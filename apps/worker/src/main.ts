import { serviceName } from "./index.js";

process.stdout.write(`${serviceName} worker ready\n`);
setInterval(() => undefined, 60_000);
