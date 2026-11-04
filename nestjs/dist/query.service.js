"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.QueryService = void 0;
const common_1 = require("@nestjs/common");
let QueryService = class QueryService {
    fastApiUrl = process.env.FASTAPI_URL ?? "http://api:8000";
    apiKey = process.env.API_KEY ?? "";
    async forward(request) {
        if (!request.query?.trim()) {
            throw new common_1.BadRequestException("query must not be empty");
        }
        try {
            const response = await fetch(`${this.fastApiUrl}/api/v1/query`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": this.apiKey,
                },
                body: JSON.stringify(request),
                signal: AbortSignal.timeout(65_000),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new common_1.BadGatewayException(payload);
            }
            return payload;
        }
        catch (error) {
            if (error instanceof common_1.BadGatewayException ||
                error instanceof common_1.BadRequestException) {
                throw error;
            }
            throw new common_1.ServiceUnavailableException("FastAPI is unavailable.", error instanceof Error ? error.message : undefined);
        }
    }
};
exports.QueryService = QueryService;
exports.QueryService = QueryService = __decorate([
    (0, common_1.Injectable)()
], QueryService);
