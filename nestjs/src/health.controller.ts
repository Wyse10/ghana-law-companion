import { Controller, Get } from "@nestjs/common";

@Controller("health")
export class HealthController {
  private get fastApiUrl(): string {
    return process.env.FASTAPI_URL || "http://127.0.0.1:8000";
  }

  @Get("live")
  live(): { status: string } {
    return { status: "ok" };
  }

  @Get("status")
  async status(): Promise<{ bff: string; fastApi: string; timestamp: string }> {
    let fastApiStatus = "unavailable";
    try {
      const res = await fetch(`${this.fastApiUrl}/health/live`, {
        signal: AbortSignal.timeout(3000),
      });
      if (res.ok) {
        fastApiStatus = "ok";
      }
    } catch {
      fastApiStatus = "unreachable";
    }

    return {
      bff: "ok",
      fastApi: fastApiStatus,
      timestamp: new Date().toISOString(),
    };
  }
}
