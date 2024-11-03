import argparse
import json
import sys
from typing import Any, Dict, Optional

import attr
import cattr
import pandas as pd
import yaml
from attr import define
from fastapi import FastAPI, HTTPException

from refactor.ds import DS

app = FastAPI()


@define
class DSSchema:
    class_: str
    id: str
    uri: str
    file: Optional[Dict[str, str]] = None  # Nested file field, optional


class FileDS(DS):
    def __init__(self, file: Dict[str, str], **kwargs):
        if 'path' not in file:
            raise ValueError("File dictionary must contain 'path' key")
        df = pd.read_csv(file['path'])
        super().__init__(df, **kwargs)


def validate_yaml(yaml_data: Dict[str, Any]) -> None:
    try:
        cattr.structure(yaml_data, DSSchema)
    except Exception as e:
        raise ValueError(f'Invalid YAML schema: {e}') from e


def create_ds(yaml_params: str) -> DS:
    try:
        ds_params = yaml.safe_load(yaml_params)
        validate_yaml(ds_params)
        if 'file' in ds_params:
            return FileDS(**ds_params)
        else:
            return DS(**ds_params)
    except yaml.YAMLError as e:
        raise ValueError(f'Invalid YAML: {e!s}') from e
    except Exception as e:
        raise ValueError(f'Error creating DS: {e!s}') from e


@app.get('/generate_ds')
async def generate_ds(yaml_params: str):
    try:
        ds = create_ds(yaml_params)
        json_data = ds.df.to_json(orient='records')
        return json.loads(json_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def generate_help_from_schema():
    help_text = 'Generate DS from YAML parameters\n\n'
    for field in attr.fields(DSSchema):
        help_text += f'{field.name}: {field.type}\n'
    return help_text


def main():
    parser = argparse.ArgumentParser(
        description=generate_help_from_schema(),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('--yaml_file', help='Path to YAML file with DS parameters')

    # Add arguments based on DSSchema
    for field in attr.fields(DSSchema):
        parser.add_argument(f'--{field.name}', help=f'{field.name} parameter')

    args = parser.parse_args()

    if args.yaml_file:
        with open(args.yaml_file, 'r') as file:
            yaml_params = file.read()
    else:
        # Create a dictionary from command-line arguments
        params = {
            k: v for k, v in vars(args).items() if v is not None and k != 'yaml_file'
        }
        yaml_params = yaml.dump(params)

    try:
        ds = create_ds(yaml_params)
        print(ds)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main()
    else:
        import uvicorn

        uvicorn.run(app, host='0.0.0.0', port=8000)
