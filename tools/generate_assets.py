import argparse
from raspberry_pi.config import DEFAULT_CONFIG, load_config
from raspberry_pi.page_renderer import create_page_asset


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate monochrome Inklite page BMPs")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    config = load_config(args.config)
    config.assets_path.mkdir(parents=True, exist_ok=True)
    for page in config.pages:
        path = config.assets_path / (page + ".bmp")
        create_page_asset(page, (config.width, config.height)).save(path, format="BMP")
        print(f"[ASSET] {page}.bmp: {config.width}x{config.height}, 1-bit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
