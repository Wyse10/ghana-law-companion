"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const fs_1 = require("fs");
const path_1 = require("path");
const common_1 = require("@nestjs/common");
const core_1 = require("@nestjs/core");
const app_module_1 = require("./app.module");
if (!process.env.API_KEY) {
    const rootEnv = (0, path_1.resolve)(__dirname, "../../.env");
    if ((0, fs_1.existsSync)(rootEnv) && typeof process.loadEnvFile === "function") {
        try {
            process.loadEnvFile(rootEnv);
        }
        catch {
        }
    }
    else {
        const localEnv = (0, path_1.resolve)(__dirname, "../.env");
        if ((0, fs_1.existsSync)(localEnv) && typeof process.loadEnvFile === "function") {
            try {
                process.loadEnvFile(localEnv);
            }
            catch {
            }
        }
    }
}
async function bootstrap() {
    const app = await core_1.NestFactory.create(app_module_1.AppModule);
    app.setGlobalPrefix("api");
    app.useGlobalPipes(new common_1.ValidationPipe({
        whitelist: true,
        forbidNonWhitelisted: true,
        transform: true,
    }));
    const publicDir = (0, path_1.join)(__dirname, "..", "public");
    app.useStaticAssets(publicDir);
    const port = Number(process.env.PORT ?? 3000);
    await app.listen(port, "0.0.0.0");
}
void bootstrap();
