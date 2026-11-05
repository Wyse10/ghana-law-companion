import { existsSync } from "fs";
import { join, resolve } from "path";
import { ValidationPipe } from "@nestjs/common";
import { NestFactory } from "@nestjs/core";
import { NestExpressApplication } from "@nestjs/platform-express";
import { AppModule } from "./app.module";

// Automatically load project root .env if API_KEY is not already in environment
if (!process.env.API_KEY) {
  const rootEnv = resolve(__dirname, "../../.env");
  if (existsSync(rootEnv) && typeof process.loadEnvFile === "function") {
    try {
      process.loadEnvFile(rootEnv);
    } catch {
      // Ignore if unparseable
    }
  } else {
    const localEnv = resolve(__dirname, "../.env");
    if (existsSync(localEnv) && typeof process.loadEnvFile === "function") {
      try {
        process.loadEnvFile(localEnv);
      } catch {
        // Ignore if unparseable
      }
    }
  }
}

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create<NestExpressApplication>(AppModule);
  app.setGlobalPrefix("api");
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  // Serve modern client UI from public folder
  const publicDir = join(__dirname, "..", "public");
  app.useStaticAssets(publicDir);

  const port = Number(process.env.PORT ?? 3000);
  await app.listen(port, "0.0.0.0");
}

void bootstrap();
