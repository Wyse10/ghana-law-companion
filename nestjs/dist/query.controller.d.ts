import { QueryRequest, QueryService } from "./query.service";
export declare class QueryDto implements QueryRequest {
    query: string;
    top_k?: number;
    chapter?: string | null;
}
export declare class QueryController {
    private readonly queryService;
    constructor(queryService: QueryService);
    query(request: QueryDto): Promise<unknown>;
}
