#!/bin/bash
set -e
DATE=$(date +%F-%H-%M)
BACKUP_DIR="/data/backup"
mkdir -p $BACKUP_DIR

# RDB backup
docker-compose exec redis redis-cli --rdb /data/backup/dump-$DATE.rdb
# AOF backup
docker-compose exec redis cp /data/appendonly.aof /data/backup/appendonly-$DATE.aof

# Garder 7 jours
find $BACKUP_DIR -name "*.rdb" -o -name "*.aof" -mtime +7 -delete