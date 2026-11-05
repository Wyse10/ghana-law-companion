export declare class HealthController {
    private get fastApiUrl();
    live(): {
        status: string;
    };
    status(): Promise<{
        bff: string;
        fastApi: string;
        timestamp: string;
    }>;
}
