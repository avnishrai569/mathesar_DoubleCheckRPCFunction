import type { Database } from '@mathesar/AppTypes';
import { getAPI, patchAPI, type PaginatedResponse } from './utils/requestUtils';

export type Connection = Database;

interface ConnectionWithPassword extends Connection {
  password: string;
}

export type UpdatableConnectionProperties = Omit<
  ConnectionWithPassword,
  'id' | 'nickname'
>;

function list() {
  return getAPI<PaginatedResponse<Connection>>(
    '/api/db/v0/connections/?limit=500',
  );
}

function update(
  connectionId: Connection['id'],
  properties: Partial<UpdatableConnectionProperties>,
) {
  return patchAPI<Connection>(
    `/api/db/v0/connections/${connectionId}/`,
    properties,
  );
}

export default {
  list,
  update,
};
