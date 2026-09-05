import { createApiServer } from "./index.js";

const port = Number(process.env.PORT || 8080);
createApiServer().listen(port, "0.0.0.0", () => process.stdout.write(`vulcan-api listening on ${port}\n`));
