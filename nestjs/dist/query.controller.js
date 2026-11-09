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
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.QueryController = exports.QueryDto = void 0;
const common_1 = require("@nestjs/common");
const class_validator_1 = require("class-validator");
const query_service_1 = require("./query.service");
class QueryDto {
    query;
    chapter;
}
exports.QueryDto = QueryDto;
__decorate([
    (0, class_validator_1.IsString)(),
    (0, class_validator_1.MinLength)(1),
    (0, class_validator_1.MaxLength)(10_000),
    __metadata("design:type", String)
], QueryDto.prototype, "query", void 0);
__decorate([
    (0, class_validator_1.IsOptional)(),
    (0, class_validator_1.IsString)(),
    (0, class_validator_1.MaxLength)(20),
    __metadata("design:type", Object)
], QueryDto.prototype, "chapter", void 0);
let QueryController = class QueryController {
    queryService;
    constructor(queryService) {
        this.queryService = queryService;
    }
    query(request) {
        return this.queryService.forward(request);
    }
};
exports.QueryController = QueryController;
__decorate([
    (0, common_1.Post)("query"),
    (0, common_1.HttpCode)(common_1.HttpStatus.OK),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [QueryDto]),
    __metadata("design:returntype", void 0)
], QueryController.prototype, "query", null);
exports.QueryController = QueryController = __decorate([
    (0, common_1.Controller)(),
    __metadata("design:paramtypes", [query_service_1.QueryService])
], QueryController);
