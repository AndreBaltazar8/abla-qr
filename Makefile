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

.PHONY: test test-in-shell examples interop interop-programs interop-in-shell clean

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
	nix-shell $(NIXPKGS_IMPORT) $(ABLAC_DIR)/shell.nix --run '$(MAKE) interop-programs'
	nix-shell $(NIXPKGS_IMPORT) tools/interop-shell.nix --run '$(MAKE) interop-in-shell'

# The inputs of the interoperability checks, made by Abla programs.
interop-programs:
	$(COMPILER) build tools/interop-payloads.ab -o $(BUILD_DIR)/interop-payloads
	$(BUILD_DIR)/interop-payloads $(BUILD_DIR)/interop-payload-files
	$(COMPILER) build tools/make-fixtures.ab -o $(BUILD_DIR)/make-fixtures
	$(BUILD_DIR)/make-fixtures $(INTEROP_DIR)

# zbar and rsvg-convert read what qrtool wrote; qrtool reads the fixtures.
interop-in-shell:
	bash tools/interop-create.sh $(BUILD_DIR)/qrtool $(BUILD_DIR)/interop-payload-files
	bash tools/interop-read.sh $(BUILD_DIR)/qrtool '$(INTEROP_DIR) tests/interop/other-encoders' $(ALLOWED)

clean:
	@if [ -d "$(BUILD_DIR)" ]; then gio trash "$(BUILD_DIR)"; fi
