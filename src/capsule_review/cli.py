"""Local viewer, bounded data downloads and reproducible anatomy baselines."""

import argparse
import json
from pathlib import Path

from .app import create_app
from .baseline_data import ANATOMY_CLASSES, prepare_manifest, read_json
from .importer import create_demo, import_folder
from .prediction_service import save_predictions
from .store import Store


def main():
    parser = argparse.ArgumentParser(prog='capsule-review')
    parser.add_argument('--data-dir', type=Path, default=Path.home() / '.capsule-review',
                        help='Persistent local workspace (default: ~/.capsule-review)')
    commands = parser.add_subparsers(dest='command', required=True)
    serve = commands.add_parser('serve', help='Start the browser application on localhost')
    serve.add_argument('--port', type=int, default=8765)
    commands.add_parser('demo', help='Import non-medical test images')
    commands.add_parser('studies', help='List imported examinations and their IDs')
    imp = commands.add_parser('import', help='Import local research images')
    imp.add_argument('folder', type=Path)
    imp.add_argument('--title', required=True)
    imp.add_argument('--source', default='Local research images')
    imp.add_argument('--labels', type=Path, help='Optional Galar frame CSV; stored as reference only')

    data = commands.add_parser('data', help='Inspect or download selected official Galar files')
    data_cmd = data.add_subparsers(dest='data_command', required=True)
    catalog = data_cmd.add_parser('catalog', help='List official file names, IDs, sizes and checksums')
    catalog.add_argument('--output', type=Path, required=True)
    download = data_cmd.add_parser('download', help='Download exactly one selected file with a size limit')
    download.add_argument('--catalog', type=Path, required=True)
    download.add_argument('--file-id', type=int, required=True)
    download.add_argument('--destination', type=Path, required=True)
    download.add_argument('--max-mib', type=int, default=512)

    model = commands.add_parser('baseline', help='Prepare, train and run a local anatomy classifier')
    model_cmd = model.add_subparsers(dest='model_command', required=True)
    prepare = model_cmd.add_parser('prepare', help='Create an explicit examination-separated development manifest')
    prepare.add_argument('--images', type=Path, required=True)
    prepare.add_argument('--annotations', type=Path, required=True)
    prepare.add_argument('--validation-exams', required=True, help='Comma-separated examination IDs, all in 1–60')
    prepare.add_argument('--output', type=Path, required=True)
    prepare.add_argument('--max-frames-per-exam', type=int, default=512)
    prepare.add_argument('--classes', nargs='+', choices=ANATOMY_CLASSES, default=list(ANATOMY_CLASSES))
    prepare.add_argument('--patient-groups', type=Path, help='Optional de-identified JSON map: examination ID to group ID')
    prepare.add_argument('--data-kind', choices=['galar', 'synthetic-test'], default='galar')
    train = model_cmd.add_parser('train', help='Fit a compact CNN and compare it with a majority baseline')
    train.add_argument('--manifest', type=Path, required=True)
    train.add_argument('--images', type=Path, required=True)
    train.add_argument('--output', type=Path, required=True)
    train.add_argument('--epochs', type=int, default=10)
    train.add_argument('--batch-size', type=int, default=32)
    train.add_argument('--learning-rate', type=float, default=0.001)
    train.add_argument('--seed', type=int, default=17)
    train.add_argument('--device', choices=['cpu', 'cuda', 'mps'], default='cpu')
    train.add_argument('--allow-synthetic-test', action='store_true')
    install = model_cmd.add_parser('install', help='Install your completed local model for the browser')
    install.add_argument('run', type=Path)
    install.add_argument('--allow-synthetic-test', action='store_true', help='Software testing only; never enables use on real exams')
    predict = model_cmd.add_parser('predict', help='Run a completed model and save suggestions into the viewer')
    predict.add_argument('run', type=Path)
    predict.add_argument('--study', required=True)
    predict.add_argument('--allow-training-overlap', action='store_true', help='Explicitly mark output as an in-sample demonstration')
    predict.add_argument('--allow-synthetic-test', action='store_true')
    args = parser.parse_args()
    if args.command == 'serve':
        if not 1024 <= args.port <= 65535:
            parser.error('Choose a port between 1024 and 65535.')
        import uvicorn
        print(f'Open http://127.0.0.1:{args.port} — data stays in {args.data_dir.expanduser()}')
        uvicorn.run(create_app(args.data_dir), host='127.0.0.1', port=args.port, log_level='warning')
        return
    try:
        if args.command == 'data':
            from .data_download import download_file, get_catalog
            if args.data_command == 'catalog':
                result = get_catalog(args.output)
                print(f'Galar version {result["version"]}; license: {result.get("license", {}).get("name", "check record")}')
                print('ID\tMiB\tFile')
                for item in result['files']:
                    print(f'{item["id"]}\t{item["size"] / 1024**2:.2f}\t{item["name"]}')
                return
            result = download_file(read_json(args.catalog), args.file_id, args.destination,
                                   max_bytes=args.max_mib * 1024**2)
        elif args.command == 'baseline':
            if args.model_command == 'prepare':
                groups = read_json(args.patient_groups) if args.patient_groups else None
                manifest = prepare_manifest(args.images, args.annotations, args.output,
                    validation_exams=[int(n.strip()) for n in args.validation_exams.split(',')],
                    max_frames_per_exam=args.max_frames_per_exam, classes=tuple(args.classes),
                    data_kind=args.data_kind, patient_groups=groups)
                result = {key: manifest[key] for key in ['manifest_sha256', 'data_kind', 'split_unit', 'counts', 'examinations']}
            else:
                from . import baseline
                if args.model_command == 'train':
                    result = baseline.train(args.manifest, args.images, args.output, epochs=args.epochs,
                        batch_size=args.batch_size, learning_rate=args.learning_rate, seed=args.seed,
                        device=args.device, allow_synthetic_test=args.allow_synthetic_test)
                elif args.model_command == 'install':
                    result = {'model_id': baseline.install_model(Store(args.data_dir), args.run,
                              allow_synthetic_test=args.allow_synthetic_test)}
                else:
                    store = Store(args.data_dir)
                    payload = baseline.predict_study(store, args.study, args.run,
                        allow_training_overlap=args.allow_training_overlap,
                        allow_synthetic_test=args.allow_synthetic_test)
                    result = save_predictions(store, args.study, payload)
        else:
            store = Store(args.data_dir)
            if args.command == 'studies':
                with store.connect() as db:
                    result = [dict(row) for row in db.execute('SELECT id,title,frame_count,synthetic FROM studies ORDER BY created_at')]
            elif args.command == 'demo':
                result = create_demo(store)
            else:
                result = import_folder(store, args.folder, title=args.title, source=args.source, labels=args.labels)
        print(json.dumps(result, indent=2, allow_nan=False))
    except ImportError as exc:
        parser.exit(1, f'Missing optional dependency: {exc}. Install with: python -m pip install -e ".[ml]"\n')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Operation stopped: {exc}\n')


if __name__ == '__main__':
    main()
