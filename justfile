# lint files
lint:
    prek run --all-files

# run the tests
test:
    python3 -m unittest discover -s validate-min-terraform -p 'test_*.py'
