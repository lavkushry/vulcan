import { createApiServer } from "./index.js";
import pg from "pg";
import { PostgresBoardStore, PostgresIdentityStore } from "@vulcan/domain";
import { readFile } from "node:fs/promises";

const port = Number(process.env.PORT || 8080);
const connectionString = process.env.DATABASE_URL;
const client = connectionString ? new pg.Client({ connectionString }) : undefined;
if (client) {
  await client.connect();
  for (const migration of ["migrations/001_whiteboard.sql", "migrations/002_identity_ai_audit.sql"]) {
    await client.query(await readFile(migration, "utf8"));
  }
}
const server = createApiServer(undefined, undefined, client ? new PostgresBoardStore(client) : undefined, {}, client ? new PostgresIdentityStore(client) : undefined);
server.listen(port, "0.0.0.0", () => process.stdout.write(`vulcan-api listening on ${port}${client ? " with PostgreSQL" : " with in-memory storage"}\n`));
