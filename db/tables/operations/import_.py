import tempfile
import clevercsv as csv
from db.tables.operations.create import prepare_table_for_import
from db.encoding_utils import get_sql_compatible_encoding
from mathesar.models.deprecated import DataFile
from mathesar.imports.csv import get_file_encoding, get_sv_reader, process_column_names


def import_csv(data_file_id, table_name, schema_oid, conn, comment=None):
    data_file = DataFile.objects.get(id=data_file_id)
    file_path = data_file.file.path
    header = data_file.header
    dialect = csv.dialect.SimpleDialect(
        data_file.delimiter,
        data_file.quotechar,
        data_file.escapechar
    )
    encoding = get_file_encoding(data_file.file)
    conversion_encoding, sql_encoding = get_sql_compatible_encoding(encoding)
    with open(file_path, 'rb') as csv_file:
        csv_reader = get_sv_reader(csv_file, header, dialect)
        column_names = process_column_names(csv_reader.fieldnames)
    copy_sql, table_oid = prepare_table_for_import(
        table_name,
        schema_oid,
        column_names,
        header,
        conn,
        dialect.delimiter,
        dialect.escapechar,
        dialect.quotechar,
        sql_encoding,
        comment
    )
    insert_csv_records(
        copy_sql,
        file_path,
        encoding,
        conversion_encoding,
        conn
    )
    return table_oid


def insert_csv_records(
    copy_sql,
    file_path,
    encoding,
    conversion_encoding,
    conn
):
    cursor = conn.cursor()
    with open(file_path, 'r', encoding=encoding) as csv_file:
        if conversion_encoding == encoding:
            with cursor.copy(copy_sql) as copy:
                while data := csv_file.read():
                    copy.write(data)
        else:
            # File needs to be converted to compatible database supported encoding
            with tempfile.SpooledTemporaryFile(mode='wb+', encoding=conversion_encoding) as temp_file:
                while True:
                    contents = csv_file.read().encode(conversion_encoding, "replace")
                    if not contents:
                        break
                    temp_file.write(contents)
                temp_file.seek(0)
                with cursor.copy(copy_sql) as copy:
                    while data := temp_file.read():
                        copy.write(data)