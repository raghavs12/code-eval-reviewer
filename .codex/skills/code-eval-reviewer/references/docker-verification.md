# Docker Verification (exact commands)

Run these commands exactly and in order. Do not wait for user prompting.

```bash
git apply "problem/test.patch"

docker build -t shipd/<repo-name> -f "problem/dockerfile" .

docker run -it --network=none shipd/<repo-name>
# inside docker:
sed -i 's/\r$//' ./test.sh
./test.sh base  # must pass
./test.sh new   # must fail

git apply "problem/solution.patch"

docker build -t shipd/<repo-name> -f "problem/dockerfile" .

docker run -it --network=none shipd/<repo-name>
# inside docker:
sed -i 's/\r$//' ./test.sh
./test.sh base  # must pass
./test.sh new   # must pass
```

Replace `<repo-name>` with the actual repository name when running these commands.
Do not edit any problem files or other code while running Docker verification.
