docker run --gpus 0 --rm --network=host -p 8888:8888 -e JUPYTER_ENABLE_LAB=yes -v /home/finnweng/ExtStorage:/home/workspace -it tensorflow/tensorflow:my_latest
