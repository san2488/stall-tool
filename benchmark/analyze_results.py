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
            row['total_bedrock_requests'] = int(row.get('total_bedrock_requests', 0))
            row['cross_region_requests'] = int(row.get('cross_region_requests', 0))
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
        'tool_calls_count': [],
        'cross_region_pct': []
    })
    
    for row in results:
        if row['status'] == 'success':
            task_type = row['task_type']
            grouped[task_type]['first_token_ms'].append(row['first_token_ms'])
            grouped[task_type]['total_task_ms'].append(row['total_task_ms'])
            grouped[task_type]['max_turn_ms'].append(row['max_turn_ms'])
            grouped[task_type]['tool_calls_count'].append(row['tool_calls_count'])
            
            # Calculate cross-region percentage for this task
            total_requests = row.get('total_bedrock_requests', 0)
            cross_region = row.get('cross_region_requests', 0)
            if total_requests > 0:
                pct = (cross_region / total_requests) * 100
                grouped[task_type]['cross_region_pct'].append(pct)
    
    stats = {}
    for task_type, metrics in grouped.items():
        stats[task_type] = {
            'first_token': calculate_stats(metrics['first_token_ms']),
            'total_task': calculate_stats(metrics['total_task_ms']),
            'max_turn': calculate_stats(metrics['max_turn_ms']),
            'tool_calls': calculate_stats(metrics['tool_calls_count']),
            'cross_region_pct': calculate_stats(metrics['cross_region_pct']) if metrics['cross_region_pct'] else {}
        }
    
    return stats


def analyze_cross_region_impact(bedrock_results):
    """Analyze latency impact of cross-region requests.
    
    Args:
        bedrock_results: List of Bedrock result rows
        
    Returns:
        Dict with cross-region vs same-region statistics
    """
    same_region = defaultdict(list)
    cross_region = defaultdict(list)
    
    for row in bedrock_results:
        if row['status'] != 'success':
            continue
        
        total_requests = row.get('total_bedrock_requests', 0)
        cross_requests = row.get('cross_region_requests', 0)
        
        if total_requests == 0:
            continue
        
        task_type = row['task_type']
        
        # Categorize as same-region or cross-region
        if cross_requests == 0:
            # All requests were same-region
            same_region[task_type].append({
                'first_token_ms': row['first_token_ms'],
                'total_task_ms': row['total_task_ms'],
                'max_turn_ms': row['max_turn_ms']
            })
        elif cross_requests == total_requests:
            # All requests were cross-region
            cross_region[task_type].append({
                'first_token_ms': row['first_token_ms'],
                'total_task_ms': row['total_task_ms'],
                'max_turn_ms': row['max_turn_ms']
            })
        # Skip mixed requests for cleaner comparison
    
    # Calculate statistics
    stats = {}
    for task_type in set(list(same_region.keys()) + list(cross_region.keys())):
        stats[task_type] = {}
        
        if task_type in same_region:
            same_data = same_region[task_type]
            stats[task_type]['same_region'] = {
                'first_token': calculate_stats([r['first_token_ms'] for r in same_data]),
                'total_task': calculate_stats([r['total_task_ms'] for r in same_data]),
                'max_turn': calculate_stats([r['max_turn_ms'] for r in same_data])
            }
        
        if task_type in cross_region:
            cross_data = cross_region[task_type]
            stats[task_type]['cross_region'] = {
                'first_token': calculate_stats([r['first_token_ms'] for r in cross_data]),
                'total_task': calculate_stats([r['total_task_ms'] for r in cross_data]),
                'max_turn': calculate_stats([r['max_turn_ms'] for r in cross_data])
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


def print_summary(bedrock_stats, anthropic_stats, comparison, cross_region_stats=None):
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
        
        # Print cross-region stats if available
        if cross_region_stats and task_type in cross_region_stats:
            cr_stats = cross_region_stats[task_type]
            
            # Print cross-region percentage
            if 'cross_region_pct' in bedrock_stats[task_type]:
                pct_stats = bedrock_stats[task_type]['cross_region_pct']
                if pct_stats:
                    print(f"\nCross-Region Requests: {pct_stats.get('mean', 0):.1f}% (avg)")
            
            # Compare same-region vs cross-region latency
            if 'same_region' in cr_stats and 'cross_region' in cr_stats:
                print("\nSame-Region vs Cross-Region Latency:")
                for metric in ['first_token', 'max_turn', 'total_task']:
                    same = cr_stats['same_region'][metric]['mean']
                    cross = cr_stats['cross_region'][metric]['mean']
                    diff = cross - same
                    pct_diff = (diff / same * 100) if same > 0 else 0
                    
                    metric_name = metric.replace('_', ' ').title()
                    print(f"  {metric_name:18s}: Same={same:7.1f}ms  Cross={cross:7.1f}ms  "
                          f"Diff={diff:+7.1f}ms ({pct_diff:+.1f}%)")


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
    
    # Analyze cross-region impact
    cross_region_stats = analyze_cross_region_impact(bedrock_results)
    
    # Save comparison
    output_file = results_dir / 'comparison_report.csv'
    save_comparison_csv(comparison, output_file)
    print(f"\n✓ Comparison saved to {output_file}")
    
    # Print summary
    print_summary(bedrock_stats, anthropic_stats, comparison, cross_region_stats)
    
    # Save detailed JSON
    json_output = results_dir / 'detailed_stats.json'
    with open(json_output, 'w') as f:
        json.dump({
            'bedrock': bedrock_stats,
            'anthropic': anthropic_stats,
            'comparison': comparison,
            'cross_region': cross_region_stats
        }, f, indent=2)
    print(f"\n✓ Detailed stats saved to {json_output}")


if __name__ == '__main__':
    main()
