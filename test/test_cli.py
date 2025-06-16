import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from click.testing import CliRunner
import logging

from loam_iiif.cli import sanitize_filename, collect, cli

@pytest.fixture
def cli_runner():
    return CliRunner()

@pytest.fixture
def mock_iiif_client():
    with patch('loam_iiif.cli.IIIFClient') as mock:
        # Setup mock instance
        instance = mock.return_value.__enter__.return_value
        instance.get_manifests_and_collections_ids.return_value = (
            ["http://example.com/manifest1", "http://example.com/manifest2"],
            ["http://example.com/collection1"]
        )
        instance.get_manifest_images.return_value = [
            "http://example.com/image1.jpg",
            "http://example.com/image2.jpg"
        ]
        instance.fetch_json.return_value = {"some": "manifest"}
        yield instance

@pytest.mark.parametrize('debug_message', [
    'Starting traversal of IIIF collection: http://example.com/collection',
    'Using cache directory:',
    'Processing 2 manifests for image URLs',
    'Traversal completed. Found 2 unique manifests and 1 collections.'
])
def test_debug_logging(cli_runner, mock_iiif_client, caplog, debug_message):
    """Test that debug messages are logged when debug flag is enabled"""
    with caplog.at_level(logging.DEBUG):
        result = cli_runner.invoke(cli, [
            'collect',
            'http://example.com/collection',
            '--debug',
            '--images'
        ])
        
        assert result.exit_code == 0
        # Check if the debug message appears in the logs
        assert any(debug_message in record.message for record in caplog.records)

def test_debug_manifest_download_logging(cli_runner, mock_iiif_client, caplog, tmp_path):
    """Test debug logging for manifest downloads"""
    output_dir = tmp_path / "manifests"
    with caplog.at_level(logging.DEBUG):
        result = cli_runner.invoke(cli, [
            'collect',
            'http://example.com/collection',
            '--debug',
            '--download-manifests',
            '-o', str(output_dir)
        ])
        
        assert result.exit_code == 0
        # Verify specific debug messages for manifest downloads
        assert any('Downloading JSON contents for 2 manifests' in record.message 
                  for record in caplog.records)
        assert any('Will save manifest files to directory:' in record.message 
                  for record in caplog.records)
        assert any('All manifests have been saved to' in record.message 
                  for record in caplog.records)

def test_collect_manifest_cache_debug_logging(cli_runner, mock_iiif_client, caplog):
    """Test debug logging when manifests are cached but not downloaded to output"""
    with caplog.at_level(logging.DEBUG):
        result = cli_runner.invoke(cli, [
            'collect',
            'http://example.com/collection',
            '--debug',
            '--download-manifests'
        ])
        
        assert result.exit_code == 0
        assert any(
            f'All manifests have been cached to' in record.message
            for record in caplog.records
        )

def test_error_logging(cli_runner, mock_iiif_client, caplog):
    """Test error logging when getting images fails"""
    mock_iiif_client.get_manifest_images.side_effect = Exception("Test image error")
    
    with caplog.at_level(logging.ERROR):
        result = cli_runner.invoke(cli, [
            'collect',
            'http://example.com/collection',
            '--debug',
            '--images'
        ])
        
        assert result.exit_code == 0
        assert any('Error getting images from manifest' in record.message 
                  for record in caplog.records)

def test_sanitize_filename():
    """Test the sanitize_filename function with realistic manifest URL filenames"""
    test_cases = [
        ("manifest.json", "manifest.json"),
        ("iiif-manifest.json", "iiif-manifest.json"),
        ("123_456.json", "123_456.json"),
        ("manifest with spaces.json", "manifest_with_spaces.json"),
        ("manifest.v2.json", "manifest.v2.json"),
        ("collection@2x.json", "collection_2x.json"),
    ]
    
    for input_name, expected in test_cases:
        assert sanitize_filename(input_name) == expected

def test_collect_basic_json_output(cli_runner, mock_iiif_client, tmp_path):
    """Test basic collect command with JSON output"""
    result = cli_runner.invoke(cli, ['collect', 'http://example.com/collection', '-f', 'json'])
    
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert 'manifests' in output
    assert 'collections' in output
    assert len(output['manifests']) == 2
    assert len(output['collections']) == 1

def test_collect_with_images(cli_runner, mock_iiif_client):
    """Test collect command with images flag"""
    result = cli_runner.invoke(cli, [
        'collect', 
        'http://example.com/collection',
        '--images',
        '-f', 'json'
    ])
    
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert 'manifests' in output
    assert all('images' in manifest for manifest in output['manifests'])

def test_collect_with_manifest_download(cli_runner, mock_iiif_client, tmp_path):
    """Test collect command with manifest download option"""
    output_dir = tmp_path / "manifests"
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '--download-manifests',
        '-o', str(output_dir)
    ])
    
    assert result.exit_code == 0
    assert output_dir.exists()
    # Should have created files for both manifests
    assert len(list(output_dir.glob('*.json'))) == 2

def test_collect_jsonl_format(cli_runner, mock_iiif_client):
    """Test collect command with JSONL output format"""
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '-f', 'jsonl'
    ])
    
    assert result.exit_code == 0
    lines = result.output.strip().split('\n')
    assert len(lines) == 3  # 2 manifests + 1 collection
    # Verify each line is valid JSON
    for line in lines:
        data = json.loads(line)
        assert 'manifest' in data or 'collection' in data

def test_collect_table_format(cli_runner, mock_iiif_client):
    """Test collect command with table output format"""
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '-f', 'table'
    ])
    
    assert result.exit_code == 0
    assert 'Manifests' in result.output
    assert 'Collections' in result.output

def test_collect_table_format_with_images(cli_runner, mock_iiif_client):
    """Test collect command with table output format including image counts"""
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '-f', 'table',
        '--images'
    ])
    
    assert result.exit_code == 0
    output = result.output
    assert 'Manifests' in output
    assert 'Collections' in output
    assert 'Image Count' in output  # Verify image count column exists
    assert '2' in output  # Each manifest should show 2 images count

def test_collect_table_format_without_images(cli_runner, mock_iiif_client):
    """Test collect command with table output format without image counts"""
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '-f', 'table'
    ])
    
    assert result.exit_code == 0
    output = result.output
    assert 'Manifests' in output
    assert 'Collections' in output
    assert 'Image Count' not in output  # Verify image count column is not present

def test_collect_with_max_manifests(cli_runner, mock_iiif_client):
    """Test collect command with max manifests limit"""
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '--max-manifests', '1',
        '-f', 'json'
    ])
    
    assert result.exit_code == 0
    mock_iiif_client.get_manifests_and_collections_ids.assert_called_with(
        'http://example.com/collection',
        1
    )

@pytest.mark.parametrize('cache_option', [
    '--skip-cache',
    '--no-cache'
])
def test_collect_cache_options(cli_runner, mock_iiif_client, cache_option):
    """Test collect command with different cache options"""
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        cache_option
    ])
    
    assert result.exit_code == 0

def test_collect_with_custom_image_params(cli_runner, mock_iiif_client):
    """Test collect command with custom image parameters"""
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '--images',
        '--width', '100',
        '--height', '100',
        '--image-format', 'png'
    ])
    
    assert result.exit_code == 0
    # Check that all calls to get_manifest_images used the correct parameters
    for args, kwargs in mock_iiif_client.get_manifest_images.call_args_list:
        assert kwargs == {
            'width': 100,
            'height': 100,
            'format': 'png',
            'exact': False,
            'use_max': False
        }

def test_collect_with_debug(cli_runner, mock_iiif_client):
    """Test collect command with debug flag"""
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '--debug'
    ])
    
    assert result.exit_code == 0

def test_collect_with_error(cli_runner):
    """Test collect command error handling"""
    with patch('loam_iiif.cli.IIIFClient') as mock:
        instance = mock.return_value.__enter__.return_value
        instance.get_manifests_and_collections_ids.side_effect = Exception("Test error")
        
        result = cli_runner.invoke(cli, [
            'collect',
            'http://example.com/collection'
        ])
        
        assert result.exit_code == 1
        assert "Test error" in result.output

def test_collect_json_file_output(cli_runner, mock_iiif_client, tmp_path, caplog):
    """Test collect command writing JSON output to a file"""
    output_file = tmp_path / "output.json"
    
    with caplog.at_level(logging.DEBUG):
        result = cli_runner.invoke(cli, [
            'collect',
            'http://example.com/collection',
            '-f', 'json',
            '--debug',
            '-o', str(output_file)
        ])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        # Verify file contents
        content = json.loads(output_file.read_text())
        assert 'manifests' in content
        assert 'collections' in content
        
        # Verify debug log message
        assert any(f"Results saved to {output_file}" in record.message 
                  for record in caplog.records)

def test_collect_json_file_output_error(cli_runner, mock_iiif_client, tmp_path, caplog):
    """Test collect command handling IOError when writing JSON output"""
    # Create a directory with the same name to cause an IOError
    output_path = tmp_path / "output.json"
    output_path.mkdir()
    
    with caplog.at_level(logging.ERROR):
        result = cli_runner.invoke(cli, [
            'collect',
            'http://example.com/collection',
            '-f', 'json',
            '-o', str(output_path)
        ])
        
        assert result.exit_code == 1
        # Verify error log message
        assert any(f"Failed to write to file {output_path}" in record.message 
                  for record in caplog.records)

def test_collect_jsonl_file_output(cli_runner, mock_iiif_client, tmp_path, caplog):
    """Test collect command writing JSONL output to a file"""
    output_file = tmp_path / "output.jsonl"
    
    with caplog.at_level(logging.DEBUG):
        result = cli_runner.invoke(cli, [
            'collect',
            'http://example.com/collection',
            '-f', 'jsonl',
            '--debug',
            '--images',
            '-o', str(output_file)
        ])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        # Read and verify file contents
        lines = output_file.read_text().strip().split('\n')
        assert len(lines) == 3  # 2 manifests + 1 collection
        
        # Check manifest lines
        manifest_lines = [json.loads(line) for line in lines if 'manifest' in line]
        assert len(manifest_lines) == 2
        for line in manifest_lines:
            assert 'manifest' in line
            assert 'images' in line
        
        # Check collection line
        collection_lines = [json.loads(line) for line in lines if 'collection' in line]
        assert len(collection_lines) == 1
        assert 'collection' in collection_lines[0]
        
        # Verify debug log message
        assert any(f"JSON Lines results saved to {output_file}" in record.message 
                  for record in caplog.records)

def test_collect_jsonl_file_output_error(cli_runner, mock_iiif_client, tmp_path, caplog):
    """Test collect command handling IOError when writing JSONL output"""
    # Create a directory with the same name to cause an IOError
    output_path = tmp_path / "output.jsonl"
    output_path.mkdir()
    
    with caplog.at_level(logging.ERROR):
        result = cli_runner.invoke(cli, [
            'collect',
            'http://example.com/collection',
            '-f', 'jsonl',
            '-o', str(output_path)
        ])
        
        assert result.exit_code == 1
        # Verify error log message
        assert any(f"Failed to write to file {output_path}" in record.message 
                  for record in caplog.records)

def test_collect_jsonl_file_output_basic(cli_runner, mock_iiif_client, tmp_path):
    """Test basic JSONL file output without images or debug flags"""
    output_file = tmp_path / "output.jsonl"
    
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '-f', 'jsonl',
        '-o', str(output_file)
    ])
    
    assert result.exit_code == 0
    assert output_file.exists()
    
    # Read and verify file contents
    lines = output_file.read_text().strip().split('\n')
    assert len(lines) == 3  # 2 manifests + 1 collection
    
    # Verify manifest lines are simple format without images
    manifest_lines = [json.loads(line) for line in lines if 'manifest' in line]
    assert len(manifest_lines) == 2
    for line in manifest_lines:
        assert isinstance(line['manifest'], str)
        assert 'images' not in line
    
    # Verify collection line
    collection_lines = [json.loads(line) for line in lines if 'collection' in line]
    assert len(collection_lines) == 1
    assert isinstance(collection_lines[0]['collection'], str)

def test_collect_manifest_download_error_handling(cli_runner, mock_iiif_client, tmp_path, caplog):
    """Test error handling when downloading manifest JSON fails"""
    output_dir = tmp_path / "manifests"
    
    # Setup mock to raise an exception when fetching manifest JSON
    mock_iiif_client.fetch_json.side_effect = Exception("Failed to download manifest")
    
    with caplog.at_level(logging.ERROR):
        result = cli_runner.invoke(cli, [
            'collect',
            'http://example.com/collection',
            '--debug',
            '--download-manifests',
            '-o', str(output_dir)
        ])
        
        assert result.exit_code == 0  # Command should complete despite errors
        # Verify error was logged
        assert any(
            'Failed to download manifest http://example.com/manifest' in record.message 
            for record in caplog.records
        )

def test_collect_jsonl_stdout_with_images(cli_runner, mock_iiif_client):
    """Test collect command printing JSONL with images to stdout"""
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '-f', 'jsonl',
        '--images'
    ])
    
    assert result.exit_code == 0
    lines = result.output.strip().split('\n')
    assert len(lines) == 3  # 2 manifests + 1 collection
    
    # Verify manifest lines include images
    manifest_lines = [json.loads(line) for line in lines if 'manifest' in line]
    assert len(manifest_lines) == 2
    for line in manifest_lines:
        assert 'manifest' in line
        assert 'images' in line
        assert isinstance(line['manifest'], str)
        assert isinstance(line['images'], list)
        assert line['images'] == ["http://example.com/image1.jpg", "http://example.com/image2.jpg"]

    # Verify collection line
    collection_lines = [json.loads(line) for line in lines if 'collection' in line]
    assert len(collection_lines) == 1
    assert isinstance(collection_lines[0]['collection'], str)

def test_collect_jsonl_stdout_without_images(cli_runner, mock_iiif_client):
    """Test collect command printing JSONL without images to stdout"""
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '-f', 'jsonl'
    ])
    
    assert result.exit_code == 0
    lines = result.output.strip().split('\n')
    assert len(lines) == 3  # 2 manifests + 1 collection
    
    # Verify manifest lines are simple format without images
    manifest_lines = [json.loads(line) for line in lines if 'manifest' in line]
    assert len(manifest_lines) == 2
    for line in manifest_lines:
        assert isinstance(line['manifest'], str)
        assert 'images' not in line
        assert line['manifest'] in [
            "http://example.com/manifest1",
            "http://example.com/manifest2"
        ]

    # Verify collection line
    collection_lines = [json.loads(line) for line in lines if 'collection' in line]
    assert len(collection_lines) == 1
    assert collection_lines[0]['collection'] == "http://example.com/collection1"

def test_collect_table_format_with_image_errors(cli_runner, mock_iiif_client):
    """Test table output handles manifest image fetch errors gracefully"""
    mock_iiif_client.get_manifest_images.side_effect = Exception("Failed to get images")
    
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '-f', 'table',
        '--images'
    ])
    
    assert result.exit_code == 0
    output = result.output
    assert 'Manifests' in output
    assert 'Image Count' in output
    assert '0' in output  # Failed manifests should show 0 images

def test_main_entry_point(cli_runner):
    """Test the main() entry point function"""
    with patch('loam_iiif.cli.cli') as mock_cli:
        from loam_iiif.cli import main
        main()
        mock_cli.assert_called_once()

def test_main_entry_point_actual(cli_runner):
    """Test the actual main entry point function using the CLI group"""
    result = cli_runner.invoke(cli)
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND" in result.output

def test_collect_image_size_options(cli_runner, mock_iiif_client):
    """Test that image size options are correctly passed to get_manifest_images"""
    # Test default settings
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '--images'
    ])
    assert result.exit_code == 0
    
    # Check default parameters
    for args, kwargs in mock_iiif_client.get_manifest_images.call_args_list:
        assert kwargs == {
            'width': 768,
            'height': 2000,
            'format': 'jpg',
            'exact': False,
            'use_max': False
        }

    # Reset mock
    mock_iiif_client.get_manifest_images.reset_mock()

    # Test exact dimensions
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '--images',
        '--exact'
    ])
    assert result.exit_code == 0
    
    # Check exact dimension parameters
    for args, kwargs in mock_iiif_client.get_manifest_images.call_args_list:
        assert kwargs == {
            'width': 768,
            'height': 2000,
            'format': 'jpg',
            'exact': True,
            'use_max': False
        }

    # Reset mock
    mock_iiif_client.get_manifest_images.reset_mock()

    # Test max size
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '--images',
        '--max'
    ])
    assert result.exit_code == 0
    
    # Check max size parameters
    for args, kwargs in mock_iiif_client.get_manifest_images.call_args_list:
        assert kwargs == {
            'width': 768,
            'height': 2000,
            'format': 'jpg',
            'exact': False,
            'use_max': True
        }

    # Reset mock
    mock_iiif_client.get_manifest_images.reset_mock()

    # Test custom dimensions
    result = cli_runner.invoke(cli, [
        'collect',
        'http://example.com/collection',
        '--images',
        '--width', '100',
        '--height', '200',
        '--exact'
    ])
    assert result.exit_code == 0
    
    # Check custom dimension parameters
    for args, kwargs in mock_iiif_client.get_manifest_images.call_args_list:
        assert kwargs == {
            'width': 100,
            'height': 200,
            'format': 'jpg',
            'exact': True,
            'use_max': False
        }