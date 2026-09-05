CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY,
  email text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspaces (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'boards_workspace_id_fkey') THEN
    ALTER TABLE boards ADD CONSTRAINT boards_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS memberships (
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS memberships_user_idx ON memberships (user_id, workspace_id);

CREATE TABLE IF NOT EXISTS share_links (
  id uuid PRIMARY KEY,
  board_id uuid NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  scope text NOT NULL CHECK (scope IN ('view', 'edit')),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS share_links_board_idx ON share_links (board_id, expires_at);

CREATE TABLE IF NOT EXISTS ai_generations (
  id uuid PRIMARY KEY,
  board_id uuid NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
  status text NOT NULL CHECK (status IN ('queued', 'streaming', 'ready', 'accepted', 'rejected', 'failed')),
  prompt text NOT NULL,
  proposal jsonb,
  error_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_generations_board_idx ON ai_generations (board_id, created_at);

CREATE TABLE IF NOT EXISTS audit_ledger (
  sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  request_id text NOT NULL,
  actor_id text NOT NULL,
  action text NOT NULL,
  payload jsonb NOT NULL,
  previous_hash text NOT NULL,
  record_hash text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_ledger_request_idx ON audit_ledger (request_id, sequence);
