from frozendict import frozendict
from sqlalchemy import select
from sqlalchemy.sql.functions import count

from db.deprecated.columns import MathesarColumn
from db.deprecated.columns import get_column_name_from_attnum
from db.deprecated.tables import reflect_table_from_oid
from db.deprecated.transforms.operations import apply
from db.deprecated.transforms import base
from db.deprecated.utils import execute_pg_query
from db.deprecated.metadata import get_empty_metadata


class DBQuery:
    def __init__(
            self,
            base_table_oid,
            initial_columns,
            engine,
            transformations=None,
            name=None,
            # The same metadata will be used by all the methods within DBQuery
            # So make sure to change the metadata in case the DBQuery methods are called
            # after a mutation to the database object that could make the existing metadata invalid.
            metadata=None
    ):
        self.base_table_oid = base_table_oid
        for initial_col in initial_columns:
            assert isinstance(initial_col, InitialColumn)
        self.initial_columns = initial_columns
        self.engine = engine
        if transformations is None:
            # Less states to consider if no transformations is just an empty sequence
            transformations = tuple()
        self.transformations = transformations
        self.name = name
        self.metadata = metadata if metadata else get_empty_metadata()

    def get_input_aliases(self, ix_of_transform):
        """
        Each transformation in a DBQuery has its own list of input aliases; this returns it.
        """
        initial_aliases = self.initial_aliases
        if ix_of_transform == 0:
            return initial_aliases
        input_aliases = initial_aliases
        previous_transforms = self.transformations[:ix_of_transform]
        for transform in previous_transforms:
            output_aliases = transform.get_output_aliases(input_aliases)
            input_aliases = output_aliases
        return input_aliases

    def get_initial_column_by_input_alias(self, ix_of_transform, input_alias):
        """
        Retraces the chain of input aliases until it gets to an initial column.

        Returns None if the alias does not originate from an initial column in a way that would
        preserve a unique constraint. E.g. if it is generated by an aggregation.
        """
        initial_col_alias = \
            self._get_initial_alias_by_input_alias(ix_of_transform, input_alias)
        if initial_col_alias is None:
            return None
        initial_column = \
            self._get_initial_column_by_initial_column_alias(initial_col_alias)
        return initial_column

    def _get_initial_alias_by_input_alias(self, ix_of_transform, input_alias):
        if ix_of_transform == 0:
            return input_alias
        transforms = self.transformations[:ix_of_transform]
        initial_aliases = self.initial_aliases
        input_aliases = initial_aliases
        uc_mappings_for_each_transform = [
            transform.get_unique_constraint_mappings(input_aliases)
            for transform in transforms
        ]
        for uc_mappings in reversed(uc_mappings_for_each_transform):
            for uc_mapping in uc_mappings:
                if uc_mapping.output_alias == input_alias:
                    input_alias = uc_mapping.input_alias
                    if input_alias is None:
                        return None
                    break
        initial_alias = input_alias
        return initial_alias

    def _get_initial_column_by_initial_column_alias(self, alias):
        """
        Looks up an initial column by initial column alias; no recursive logic.
        """
        for initial_column in self.initial_columns:
            if initial_column.alias == alias:
                return initial_column

    @property
    def initial_aliases(self):
        return [
            initial_column.alias
            for initial_column
            in self.initial_columns
        ]

    # mirrors a method in db.records.operations.select
    def get_records(self, **kwargs):
        """
        Note how through this method you can perform a second batch of
        transformations. This reflects the fact that we can form a query, and
        then apply temporary transforms on it, like how you can apply
        temporary transforms to a table when in a table view.

        Also, note that we have to take care not to apply default ordering on top of the
        transformations if one of the transformations already defines an ordering (because
        that would override the transformation).
        """
        fallback_to_default_ordering = not self._is_sorting_transform_used
        final_relation = apply.apply_transformations_deprecated(
            table=self.transformed_relation,
            fallback_to_default_ordering=fallback_to_default_ordering,
            **kwargs
        )
        return execute_pg_query(self.engine, final_relation)

    @property
    def _is_sorting_transform_used(self):
        """
        Checks if any of the transforms define a sorting for the results.
        """
        return any(
            type(transform) is base.Order
            for transform
            in self.transformations
        )

    # mirrors a method in db.records.operations.select
    @property
    def count(self):
        col_name = "_count"
        relation = apply.apply_transformations_deprecated(
            table=self.transformed_relation,
            columns_to_select=[count(1).label(col_name)],
        )
        return execute_pg_query(self.engine, relation)[0][col_name]

    # NOTE if too expensive, can be rewritten to parse DBQuery spec, instead of leveraging sqlalchemy
    @property
    def all_sa_columns_map(self):
        """
        Expensive! use with care.
        """
        initial_columns_map = {
            col.name: MathesarColumn.from_column(col, engine=self.engine)
            for col in self.initial_relation.columns
        }
        output_columns_map = {
            col.name: col for col in self.sa_output_columns
        }
        transforms_columns_map = {} if self.transformations is None else {
            col.name: MathesarColumn.from_column(col, engine=self.engine)
            for i in range(len(self.transformations))
            for col in DBQuery(
                base_table_oid=self.base_table_oid,
                initial_columns=self.initial_columns,
                engine=self.engine,
                transformations=self.transformations[:i],
                name=f'{self.name}_{i}'
            ).transformed_relation.columns
        }
        map_of_alias_to_sa_col = initial_columns_map | transforms_columns_map | output_columns_map
        return map_of_alias_to_sa_col

    @property
    def sa_output_columns(self):
        """
        Sequence of SQLAlchemy columns representing the output columns of the
        relation described by this query.
        """
        return tuple(
            MathesarColumn.from_column(sa_col, engine=self.engine)
            for sa_col
            in self.transformed_relation.columns
        )

    @property
    def transformed_relation(self):
        """
        A query describes a relation. This property is the result of parsing a
        query into a relation.
        """
        transformations = self.transformations
        if transformations:
            transformed = apply.apply_transformations(
                self.initial_relation,
                transformations,
            )
            return transformed
        else:
            return self.initial_relation

    @property
    def initial_relation(self):
        metadata = self.metadata
        base_table = reflect_table_from_oid(
            self.base_table_oid, self.engine, metadata=metadata
        )
        from_clause = base_table

        # We cache aliases, because we want a given join-param subpath to have only one alias.
        map_of_jp_subpath_to_alias = {}

        # We keep track of created joins, so that we don't perform the same join more than once.
        created_joins = set()

        def _get_join_id(previous_and_this_jps):
            """
            A join (given a base table) can be uniquely identified by the JoinParameter path used to create it.
            """
            return tuple(previous_and_this_jps)

        def _process_initial_column(initial_col):
            """
            Mutably performs joins on `from_clause`, if this is not a base table initial column,
            and returns the SA column that the initial column represents.
            """
            nonlocal from_clause
            nonlocal base_table
            nonlocal map_of_jp_subpath_to_alias
            nonlocal created_joins
            jp_path = initial_col.jp_path
            right = base_table
            for i, jp in enumerate(jp_path):
                previous_jps = tuple(jp_path[:i])
                is_first_jp = len(previous_jps) == 0
                if is_first_jp:
                    left = base_table
                else:
                    left = map_of_jp_subpath_to_alias[previous_jps]
                previous_and_this_jps = tuple(previous_jps) + (jp,)
                if previous_and_this_jps in map_of_jp_subpath_to_alias:
                    right = map_of_jp_subpath_to_alias[previous_and_this_jps]
                else:
                    right = reflect_table_from_oid(
                        jp.right_oid, self.engine, metadata=metadata
                    ).alias()
                    map_of_jp_subpath_to_alias[previous_and_this_jps] = right
                left_col, right_col = jp._get_sa_cols(left, right, self.engine, metadata)
                join_id = _get_join_id(previous_and_this_jps)
                if join_id not in created_joins:
                    created_joins.add(join_id)
                    from_clause = from_clause.join(
                        right, onclause=left_col == right_col, isouter=True,
                    )
            initial_col_name = initial_col.get_name(self.engine, metadata)
            return right.columns[initial_col_name].label(initial_col.alias)

        processed_initial_columns = [
            _process_initial_column(initial_col)
            for initial_col
            in self.initial_columns
        ]
        stmt = select(processed_initial_columns).select_from(from_clause)
        return stmt.cte()

    def get_input_alias_for_output_alias(self, output_alias):
        return self.map_of_output_alias_to_input_alias.get(output_alias)

    @property
    def map_of_output_alias_to_input_alias(self):
        m = dict()
        transforms = self.transformations
        if transforms:
            for transform in transforms:
                m = m | transform.map_of_output_alias_to_input_alias
        return m


class JoinParameter:
    def __init__(
            self,
            left_oid,
            left_attnum,
            right_oid,
            right_attnum,
    ):
        self.left_oid = left_oid
        self.left_attnum = left_attnum
        self.right_oid = right_oid
        self.right_attnum = right_attnum

    def _get_sa_cols(self, left, right, engine, metadata):
        """
        Returns the left and right SA columns represented by this JoinParameter.

        It takes left and right SA from-clauses, because a JoinParameter on its own is not enough to
        identify columns. You need the context of the base table and the JoinParameter path
        (up to this JoinParameter), which are here embodied in the left and right SA from-clauses.
        """
        left_col_name = get_column_name_from_attnum(
            self.left_oid, self.left_attnum, engine, metadata=metadata
        )
        right_col_name = get_column_name_from_attnum(
            self.right_oid, self.right_attnum, engine, metadata=metadata
        )
        left_col = left.columns[left_col_name]
        right_col = right.columns[right_col_name]
        return left_col, right_col

    def __eq__(self, other):
        """Instances are equal when attributes are equal."""
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def __hash__(self):
        """Hashes are equal when attributes are equal."""
        return hash(frozendict(self.__dict__))


class InitialColumn:
    def __init__(
            self,
            # TODO consider renaming to oid; reloid is not a term we use,
            # even if it's what postgres uses; or use reloid more
            reloid,
            attnum,
            alias,
            jp_path=None,
    ):
        # alias mustn't be an empty string
        assert isinstance(alias, str) and alias.strip() != ""
        self.reloid = reloid
        self.attnum = attnum
        self.alias = alias
        if jp_path:
            for join_parameter in jp_path:
                assert type(join_parameter) is JoinParameter
        else:
            jp_path = tuple()
        self.jp_path = jp_path

    def get_name(self, engine, metadata):
        return get_column_name_from_attnum(
            self.reloid, self.attnum, engine, metadata=metadata
        )

    @property
    def is_base_column(self):
        """
        A base column is an initial column on a query's base table.
        """
        return self.jp_path is None

    def __eq__(self, other):
        """Instances are equal when attributes are equal."""
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def __hash__(self):
        """Hashes are equal when attributes are equal."""
        return hash(frozendict(self.__dict__))