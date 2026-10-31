PROJECT_DIR := $(abspath .)
ABLAC_DIR ?= $(abspath ../ablac)
COMPILER ?= $(ABLAC_DIR)/build/ablac
BUILD_DIR ?= $(PROJECT_DIR)/build
NIXPKGS_SOURCE ?= $(shell nix eval --raw nixpkgs#path)
NIXPKGS_IMPORT := -I nixpkgs=$(NIXPKGS_SOURCE)
INTEROP_DIR := $(BUILD_DIR)/interop-fixtures
# Stress categories are measured, not required. Damage is random and the worst
# cases can exceed what the level corrects.
ALLOWED := damaged=2 stress-blur=3 stress-curved=3 stress-damage=4 stress-perspective=12 stress-small=6

.PHONY: test test-in-shell examples interop interop-in-shell fixtures clean

test:
	@if [ -n "$$IN_NIX_SHELL" ]; then \
		$(MAKE) test-in-shell; \
	else \
		nix-shell $(NIXPKGS_IMPORT) $(ABLAC_DIR)/shell.nix --run '$(MAKE) test-in-shell'; \
	fi

test-in-shell: examples
	$(COMPILER) test tests

examples:
	mkdir -p $(BUILD_DIR)
	$(COMPILER) build tools/qrtool.ab -o $(BUILD_DIR)/qrtool
	$(COMPILER) build examples/create_code.ab -o $(BUILD_DIR)/create-code
	$(COMPILER) build examples/read_code.ab -o $(BUILD_DIR)/read-code
	$(BUILD_DIR)/create-code "abla-qr example" $(BUILD_DIR)/example > /dev/null
	$(BUILD_DIR)/read-code $(BUILD_DIR)/example.png | grep -q "abla-qr example"

interop: examples
	nix-shell $(NIXPKGS_IMPORT) tools/interop-shell.nix --run '$(MAKE) interop-in-shell'

interop-in-shell:
	python3 tools/interop_create.py $(BUILD_DIR)/qrtool
	python3 tools/make_fixtures.py $(INTEROP_DIR)
	python3 tools/interop_read.py $(BUILD_DIR)/qrtool $(INTEROP_DIR) $(ALLOWED)

fixtures:
	python3 tools/make_png_fixtures.py tests/fixtures/png
	nix-shell $(NIXPKGS_IMPORT) tools/interop-shell.nix --run \
		'python3 tools/make_fixtures.py tests/fixtures/photo-style --small'

clean:
	@if [ -d "$(BUILD_DIR)" ]; then gio trash "$(BUILD_DIR)"; fi
