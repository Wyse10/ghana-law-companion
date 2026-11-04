export interface QueryRequest {
    query: string;
    top_k?: number;
    chapter?: string | null;
}
export declare class QueryService {
    private readonly fastApiUrl;
    private readonly apiKey;
    forward(request: QueryRequest): Promise<unknown>;
}
