import { QueryRequest, QueryService } from "./query.service";
export declare class QueryDto implements QueryRequest {
    query: string;
    chapter?: string | null;
    session_id?: string | null;
}
export declare class QueryController {
    private readonly queryService;
    constructor(queryService: QueryService);
    query(request: QueryDto): Promise<unknown>;
    clearSession(sessionId: string): Promise<unknown>;
}
