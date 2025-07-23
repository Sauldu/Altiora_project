# src/cache/redis_cluster.py
class RedisClusterClient:
    """Redis cluster pour haute disponibilité"""
    def __init__(self, nodes: List[str]):
        self.cluster = redis.cluster.RedisCluster(
            startup_nodes=nodes,
            skip_full_coverage_check=True
        )