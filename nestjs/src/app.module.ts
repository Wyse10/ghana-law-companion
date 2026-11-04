import { Module } from "@nestjs/common";
import { HealthController } from "./health.controller";
import { QueryController } from "./query.controller";
import { QueryService } from "./query.service";

@Module({
  controllers: [HealthController, QueryController],
  providers: [QueryService],
})
export class AppModule {}
