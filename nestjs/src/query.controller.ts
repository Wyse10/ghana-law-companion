import { Body, Controller, HttpCode, HttpStatus, Post } from "@nestjs/common";
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
}

@Controller()
export class QueryController {
  constructor(private readonly queryService: QueryService) {}

  @Post("query")
  @HttpCode(HttpStatus.OK)
  query(@Body() request: QueryDto) {
    return this.queryService.forward(request);
  }
}
