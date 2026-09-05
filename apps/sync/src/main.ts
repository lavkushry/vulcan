import { serviceName } from "./index.js";

process.stdout.write(`${serviceName} ready for WebSocket connections\n`);
setInterval(() => undefined, 60_000);
