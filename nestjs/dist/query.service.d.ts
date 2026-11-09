export interface QueryRequest {
    query: string;
    chapter?: string | null;
}
export declare class QueryService {
    private get fastApiUrl();
    private get apiKey();
    forward(request: QueryRequest): Promise<unknown>;
}
