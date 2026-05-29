import asyncio
import os
import json
import time
import schedule
from loguru import logger

from aiokafka import AIOKafkaProducer
from scraper import extract_data

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "bds.raw")

SENT_POST_IDS = set()
MAX_CACHE_SIZE = 1000

async def run_crawl_job():
    global SENT_POST_IDS
    logger.info(f"[CronJob] Kích hoạt job thu thập dữ liệu: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8')
    )

    try:
        await producer.start()
    except Exception as e:
        logger.error(f"[CronJob] Không thể kết nối tới Kafka: {str(e)}")
        return

    try:
        raw_records = await extract_data(pages_to_crawl=5)
        
        # Lọc các tin trùng lặp với chu kỳ trước
        new_records = []
        for record in raw_records:
            post_id = record.get("ID")
            if post_id:
                if post_id not in SENT_POST_IDS:
                    new_records.append(record)
                    SENT_POST_IDS.add(post_id)
            else:
                # Nếu tin không có ID (trường hợp đặc biệt), vẫn gửi để tránh mất dữ liệu
                new_records.append(record)
        
        # Giới hạn kích thước cache lưu trữ ID để tránh phình bộ nhớ RAM
        if len(SENT_POST_IDS) > MAX_CACHE_SIZE:
            SENT_POST_IDS = set(list(SENT_POST_IDS)[-MAX_CACHE_SIZE // 2:])

        if not new_records:
            logger.info("[Kafka Streamed] Không phát hiện tin đăng mới nào trong chu kỳ này. Đã lọc bỏ toàn bộ tin trùng.")
            return

        logger.info(f"[CronJob] Phát hiện {len(new_records)}/{len(raw_records)} tin đăng mới. Đang gửi dữ liệu thô tới Kafka...")

        for record in new_records:
            await producer.send_and_wait(KAFKA_TOPIC, record)
        
        logger.info(f"[Kafka Streamed] Đã gửi thành công {len(new_records)} bản ghi mới vào topic: {KAFKA_TOPIC}")
    except Exception as e:
        logger.error(f"[Kafka Streamed] Lỗi khi gửi dữ liệu: {str(e)}")
    finally:
        await producer.stop()
        logger.info("[Kafka Streamed] Đã đóng kết nối với Kafka")

if __name__ == "__main__":
    # Chạy thử/kích hoạt ngay khi khởi động
    asyncio.run(run_crawl_job())
    
    schedule.every(60).seconds.do(lambda: asyncio.run(run_crawl_job()))

    while True:
        schedule.run_pending()
        time.sleep(1)
        