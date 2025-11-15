cd ..
cd Docker
docker build -t pyflink -f pyflink.Dockerfile .
docker-compose -f env-compose.yml up -d
cd ..
docker cp Scripts/llm_call.py jobmanager:/tmp/llm_call.py
docker cp Topics/Cars/Queries/Query_License_Plate_Recognition/query_license_plate_recognition_optimised_skipping.py jobmanager:/tmp/query_license_plate_recognition_optimised_skipping.py
docker exec -it docker-kafka-1 kafka-topics.sh --create --topic cars_video --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
docker exec -d jobmanager flink run -py /tmp/query_license_plate_recognition_optimised_skipping.py --pyFiles /tmp/llm_call.py
cd Topics/Cars/Data
python send_video.py
cd ../../..
cd Results
python receive_answers.py

