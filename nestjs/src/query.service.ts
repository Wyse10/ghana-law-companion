import {
  BadGatewayException,
  BadRequestException,
  Injectable,
  ServiceUnavailableException,
} from "@nestjs/common";

export interface QueryRequest {
  query: string;
  chapter?: string | null;
}

@Injectable()
export class QueryService {
  private get fastApiUrl(): string {
    return process.env.FASTAPI_URL || "http://127.0.0.1:8000";
  }

  private get apiKey(): string {
    return process.env.API_KEY || "";
  }

  async forward(request: QueryRequest): Promise<unknown> {
    if (!request.query?.trim()) {
      throw new BadRequestException("query must not be empty");
    }

    try {
      const response = await fetch(`${this.fastApiUrl}/api/v1/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": this.apiKey,
        },
        body: JSON.stringify({
          query: request.query.trim(),
          chapter: request.chapter || null,
        }),
        signal: AbortSignal.timeout(65_000),
      });
      const payload: unknown = await response.json();

      if (!response.ok) {
        throw new BadGatewayException(payload);
      }
      return payload;
    } catch (error) {
      if (
        error instanceof BadGatewayException ||
        error instanceof BadRequestException
      ) {
        throw error;
      }
      throw new ServiceUnavailableException(
        "FastAPI is unavailable.",
        error instanceof Error ? error.message : undefined,
      );
    }
  }
}
