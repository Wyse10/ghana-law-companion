import {
  Body,
  Controller,
  Delete,
  HttpCode,
  HttpStatus,
  Param,
  Post,
} from "@nestjs/common";
import {
  IsOptional,
  IsString,
  MaxLength,
  MinLength,
} from "class-validator";
import { QueryRequest, QueryService } from "./query.service";

export class QueryDto implements QueryRequest {
  @IsString()
  @MinLength(1)
  @MaxLength(10_000)
  query!: string;

  @IsOptional()
  @IsString()
  @MaxLength(20)
  chapter?: string | null;

  @IsOptional()
  @IsString()
  @MaxLength(128)
  session_id?: string | null;
}

@Controller()
export class QueryController {
  constructor(private readonly queryService: QueryService) {}

  @Post("query")
  @HttpCode(HttpStatus.OK)
  query(@Body() request: QueryDto) {
    return this.queryService.forward(request);
  }

  @Delete("session/:sessionId")
  @HttpCode(HttpStatus.OK)
  clearSession(@Param("sessionId") sessionId: string) {
    return this.queryService.clearSession(sessionId);
  }
}
