# Đường dẫn tới Python của môi trường Conda 'bds'
PYTHON = /home/coung/miniconda3/envs/bds/bin/python
KAFKA_CONTAINER = bds_kafka
BOOTSTRAP_SERVER = localhost:9092
TOPIC = bds.raw

.PHONY: help up down create-topic show-raw run-producer run-spark run-dashboard logs status

help:
	@echo "=========================================================================="
	@echo "                    BDS BIG DATA PIPELINE AUTOMATION"
	@echo "=========================================================================="
	@echo "Các lệnh hỗ trợ quản trị và vận hành hệ thống:"
	@echo "  make up            - Khởi động Docker Containers (Zookeeper, Kafka, Spark) chạy ngầm"
	@echo "  make down          - Dừng hoàn toàn hệ thống Docker Containers và dọn dẹp"
	@echo "  make create-topic  - Khởi tạo thủ công topic '$(TOPIC)' trong Kafka Broker"
	@echo "  make show-raw      - Lắng nghe và hiển thị dữ liệu thô đang có trong topic '$(TOPIC)'"
	@echo "  make run-producer  - Chạy Producer để cào dữ liệu mới đẩy vào Kafka"
	@echo "  make run-spark     - Kích hoạt Spark Streaming để xử lý, làm sạch Real-time"
	@echo "  make run-dashboard - Chạy Streamlit dashboard tại http://localhost:8501"
	@echo "  make logs          - Xem log thời gian thực của các containers"
	@echo "  make status        - Xem trạng thái hoạt động của các container Docker"
	@echo "=========================================================================="

up:
	docker compose up -d

down:
	docker compose down

create-topic:
	docker exec $(KAFKA_CONTAINER) kafka-topics --bootstrap-server $(BOOTSTRAP_SERVER) --create --topic $(TOPIC) --partitions 1 --replication-factor 1

show-raw:
	docker exec -it $(KAFKA_CONTAINER) kafka-console-consumer --bootstrap-server $(BOOTSTRAP_SERVER) --topic $(TOPIC) --from-beginning

run-producer:
	$(PYTHON) crawler/producer.py

run-spark:
	$(PYTHON) processing/spark_stream.py

run-dashboard:
	streamlit run dashboard/streamlit_app.py --server.address 0.0.0.0 --server.port 8501

logs:
	docker compose logs -f

status:
	docker ps
