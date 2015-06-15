.PHONY: dist upload test-upload

dist:
	python setup.py sdist
	python setup.py bdist_wheel --universal

upload: dist
	twine upload dist/*

test-upload: dist
	twine upload -r test dist/*

clean:
	rm -rf dist
	rm -rf build
