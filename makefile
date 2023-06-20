#Directory (change with your's path)
DATA_DIR = /home/maximilien/work/data
ANNOTATOR_DIR = /home/maximilien/work/pixano/ui/apps/annotator

all : front back

#launch back
back: 
	DATA_DIR=$(DATA_DIR) uvicorn pixano.apps.explorer.main:app &

#launch front
front :
	cd $(ANNOTATOR_DIR) && pnpm run dev

#clean all pycache dir and test parquet file
clean:
	find . \( -type d -name '__pycache__' -o -type f -name '*test*.parquet' \) -exec rm -r {} +
	rm thumb.png

