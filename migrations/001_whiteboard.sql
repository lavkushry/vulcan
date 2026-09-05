CREATE TABLE IF NOT EXISTS boards (
  id uuid PRIMARY KEY,
  workspace_id uuid NOT NULL,
  title text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS board_updates (
  board_id uuid NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
  sequence bigint NOT NULL,
  operation_id text NOT NULL,
  payload bytea NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (board_id, sequence),
  UNIQUE (board_id, operation_id)
);

CREATE TABLE IF NOT EXISTS board_snapshots (
  board_id uuid PRIMARY KEY REFERENCES boards(id) ON DELETE CASCADE,
  sequence bigint NOT NULL,
  payload bytea NOT NULL,
  checksum text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS board_updates_replay_idx ON board_updates (board_id, sequence);
