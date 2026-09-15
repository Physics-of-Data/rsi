.PHONY: java-build java-run python-run python-fresh clean

JAVA_SRC := java/src
JAVA_OUT := java/out
JAVA_LIB := java/lib/osp.jar

java-build:
	mkdir -p $(JAVA_OUT)
	javac -cp $(JAVA_LIB) -d $(JAVA_OUT) $(JAVA_SRC)/*.java

java-run: java-build
	mkdir -p results
	java -cp "$(JAVA_OUT):$(JAVA_LIB)" SHOSolverComparison

python-run:
	cd python && python3 loop.py

python-fresh:
	cd python && rm -rf checkpoints logs __pycache__ && python3 loop.py --fresh

clean:
	rm -rf $(JAVA_OUT) python/__pycache__
