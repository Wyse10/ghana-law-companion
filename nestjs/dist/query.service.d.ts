export interface QueryRequest {
    query: string;
    top_k?: number;
    chapter?: string | null;
}
export declare class QueryService {
    private get fastApiUrl();
    private get apiKey();
    forward(request: QueryRequest): Promise<unknown>;
}
