"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.HealthController = void 0;
const common_1 = require("@nestjs/common");
let HealthController = class HealthController {
    get fastApiUrl() {
        return process.env.FASTAPI_URL || "http://127.0.0.1:8000";
    }
    live() {
        return { status: "ok" };
    }
    async status() {
        let fastApiStatus = "unavailable";
        try {
            const res = await fetch(`${this.fastApiUrl}/health/live`, {
                signal: AbortSignal.timeout(3000),
            });
            if (res.ok) {
                fastApiStatus = "ok";
            }
        }
        catch {
            fastApiStatus = "unreachable";
        }
        return {
            bff: "ok",
            fastApi: fastApiStatus,
            timestamp: new Date().toISOString(),
        };
    }
};
exports.HealthController = HealthController;
__decorate([
    (0, common_1.Get)("live"),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Object)
], HealthController.prototype, "live", null);
__decorate([
    (0, common_1.Get)("status"),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], HealthController.prototype, "status", null);
exports.HealthController = HealthController = __decorate([
    (0, common_1.Controller)("health")
], HealthController);
