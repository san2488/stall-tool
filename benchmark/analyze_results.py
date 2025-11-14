"""Analyze and compare benchmark results."""
import csv
import json
from pathlib import Path
from collections import defaultdict
import statistics


def load_results(csv_file):
    """Load results from CSV file."""
    results = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            row['first_token_ms'] = float(row['first_token_ms'])
            row['stream_complete_ms'] = float(row['stream_complete_ms'])
            row['total_task_ms'] = float(row['total_task_ms'])
            row['max_turn_ms'] = float(row.get('max_turn_ms', 0))
            row['tool_calls_count'] = int(row['tool_calls_count'])
            results.append(row)
    return results


def calculate_stats(values):
    """Calculate statistics for a list of values."""
    if not values:
        return {}
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    return {
        'mean': statistics.mean(values),
        'median': statistics.median(values),
        'min': min(values),
        'max': max(values),
        'p95': sorted_values[int(n * 0.95)] if n > 0 else 0,
        'p99': sorted_values[int(n * 0.99)] if n > 0 else 0,
        'count': n
    }


def analyze_by_task_type(results):
    """Group results by task type and calculate statistics."""
    grouped = defaultdict(lambda: {
        'first_token_ms': [],
        'total_task_ms': [],
        'max_turn_ms': [],
        'tool_calls_count': []
    })
    
    for row in results:
        if row['status'] == 'success':
            task_type = row['task_type']
            grouped[task_type]['first_token_ms'].append(row['first_token_ms'])
            grouped[task_type]['total_task_ms'].append(row['total_task_ms'])
            grouped[task_type]['max_turn_ms'].append(row['max_turn_ms'])
            grouped[task_type]['tool_calls_count'].append(row['tool_calls_count'])
    
    stats = {}
    for task_type, metrics in grouped.items():
        stats[task_type] = {
            'first_token': calculate_stats(metrics['first_token_ms']),
            'total_task': calculate_stats(metrics['total_task_ms']),
            'max_turn': calculate_stats(metrics['max_turn_ms']),
            'tool_calls': calculate_stats(metrics['tool_calls_count'])
        }
    
    return stats


def compare_apis(bedrock_stats, anthropic_stats):
    """Compare Bedrock vs Anthropic statistics."""
    comparison = {}
    
    for task_type in bedrock_stats.keys():
        if task_type not in anthropic_stats:
            continue
        
        comparison[task_type] = {}
        
        for metric in ['first_token', 'max_turn', 'total_task']:
            bedrock_mean = bedrock_stats[task_type][metric]['mean']
            anthropic_mean = anthropic_stats[task_type][metric]['mean']
            
            diff = bedrock_mean - anthropic_mean
            pct_diff = (diff / anthropic_mean * 100) if anthropic_mean > 0 else 0
            
            comparison[task_type][metric] = {
                'bedrock_mean': bedrock_mean,
                'anthropic_mean': anthropic_mean,
                'diff_ms': diff,
                'pct_diff': pct_diff
            }
    
    return comparison


def save_comparison_csv(comparison, output_file):
    """Save comparison to CSV."""
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'task_type',
            'metric',
            'bedrock_mean_ms',
            'anthropic_mean_ms',
            'diff_ms',
            'pct_diff'
        ])
        
        for task_type, metrics in comparison.items():
            for metric, values in metrics.items():
                writer.writerow([
                    task_type,
                    metric,
                    f"{values['bedrock_mean']:.2f}",
                    f"{values['anthropic_mean']:.2f}",
                    f"{values['diff_ms']:.2f}",
                    f"{values['pct_diff']:.1f}%"
                ])


def print_summary(bedrock_stats, anthropic_stats, comparison):
    """Print summary to console."""
    print("\n" + "="*80)
    print("BENCHMARK RESULTS SUMMARY")
    print("="*80)
    
    for task_type in sorted(bedrock_stats.keys()):
        print(f"\n{task_type.upper()}")
        print("-" * 80)
        
        if task_type in anthropic_stats:
            comp = comparison[task_type]
            
            for metric in ['first_token', 'max_turn', 'total_task']:
                metric_name = metric.replace('_', ' ').title()
                bedrock = comp[metric]['bedrock_mean']
                anthropic = comp[metric]['anthropic_mean']
                diff = comp[metric]['diff_ms']
                pct = comp[metric]['pct_diff']
                
                print(f"{metric_name:20s}: Bedrock={bedrock:7.1f}ms  Anthropic={anthropic:7.1f}ms  "
                      f"Diff={diff:+7.1f}ms ({pct:+.1f}%)")


def main():
    """Main analysis function."""
    results_dir = Path('benchmark/results')
    
    # Check if result files exist
    bedrock_file = results_dir / 'bedrock_raw.csv'
    anthropic_file = results_dir / 'anthropic_raw.csv'
    
    if not bedrock_file.exists():
        print(f"Error: {bedrock_file} not found")
        return
    
    if not anthropic_file.exists():
        print(f"Error: {anthropic_file} not found")
        return
    
    # Load results
    print("Loading results...")
    bedrock_results = load_results(bedrock_file)
    anthropic_results = load_results(anthropic_file)
    
    print(f"Loaded {len(bedrock_results)} Bedrock results")
    print(f"Loaded {len(anthropic_results)} Anthropic results")
    
    # Analyze
    print("\nAnalyzing...")
    bedrock_stats = analyze_by_task_type(bedrock_results)
    anthropic_stats = analyze_by_task_type(anthropic_results)
    comparison = compare_apis(bedrock_stats, anthropic_stats)
    
    # Save comparison
    output_file = results_dir / 'comparison_report.csv'
    save_comparison_csv(comparison, output_file)
    print(f"\n✓ Comparison saved to {output_file}")
    
    # Print summary
    print_summary(bedrock_stats, anthropic_stats, comparison)
    
    # Save detailed JSON
    json_output = results_dir / 'detailed_stats.json'
    with open(json_output, 'w') as f:
        json.dump({
            'bedrock': bedrock_stats,
            'anthropic': anthropic_stats,
            'comparison': comparison
        }, f, indent=2)
    print(f"\n✓ Detailed stats saved to {json_output}")


if __name__ == '__main__':
    main()
