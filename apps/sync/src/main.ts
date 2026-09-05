import { GuestSessionRegistry } from "@vulcan/domain";
import { InMemoryBoardStream } from "./index.js";
import { createSyncServer } from "./server.js";

const port = Number(process.env.PORT || 8081);
const server = createSyncServer(new GuestSessionRegistry(), new InMemoryBoardStream());
server.listen(port, "0.0.0.0", () => process.stdout.write(`vulcan-sync ready for WebSocket connections on ${port}\n`));
