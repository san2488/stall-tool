"""Query CloudTrail to determine if Bedrock requests were cross-region."""
import argparse
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Set

import boto3


class CloudTrailQuerier:
    """Query CloudTrail for Bedrock InvokeModel events."""
    
    def __init__(self, region: str = 'us-east-1'):
        self.cloudtrail = boto3.client('cloudtrail', region_name=region)
        self.home_region = region
    
    def query_request_ids(self, request_ids: List[str], 
                         start_time: datetime = None,
                         end_time: datetime = None,
                         max_retries: int = 3,
                         retry_delay: int = 60) -> Dict[str, bool]:
        """Query CloudTrail for request IDs and determine if cross-region.
        
        Args:
            request_ids: List of Bedrock request IDs to query
            start_time: Start time for CloudTrail query (default: 15 min ago)
            end_time: End time for CloudTrail query (default: now)
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Delay between retries in seconds (default: 60)
            
        Returns:
            Dict mapping request_id -> is_cross_region (True if cross-region)
        """
        if not request_ids:
            return {}
        
        # Default time range: last 15 minutes
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(minutes=15)
        
        results = {}
        
        for attempt in range(max_retries + 1):
            print(f"Querying CloudTrail (attempt {attempt + 1}/{max_retries + 1}) from {start_time} to {end_time}")
            print(f"Looking for {len(request_ids)} request IDs...")
            
            # Convert request IDs to set for faster lookup
            request_id_set = set(request_ids)
            
            # Query CloudTrail events
            paginator = self.cloudtrail.get_paginator('lookup_events')
            page_iterator = paginator.paginate(
                LookupAttributes=[
                    {
                        'AttributeKey': 'EventName',
                        'AttributeValue': 'ConverseStream'
                    }
                ],
                StartTime=start_time,
                EndTime=end_time
            )
            
            events_checked = 0
            for page in page_iterator:
                for event in page.get('Events', []):
                    events_checked += 1
                    
                    # Parse CloudTrail event
                    cloud_trail_event = json.loads(event.get('CloudTrailEvent', '{}'))
                    request_id = cloud_trail_event.get('requestID')  # Note: requestID not x-amzn-requestid
                    
                    if request_id in request_id_set:
                        # Check if cross-region
                        is_cross_region = self._is_cross_region(cloud_trail_event)
                        results[request_id] = is_cross_region
                        print(f"  Found {request_id}: cross_region={is_cross_region}")
                        
                        # Stop if we found all request IDs
                        if len(results) == len(request_ids):
                            break
                
                if len(results) == len(request_ids):
                    break
            
            print(f"Checked {events_checked} CloudTrail events")
            print(f"Found {len(results)}/{len(request_ids)} request IDs")
            
            # If we found all request IDs, we're done
            if len(results) == len(request_ids):
                break
            
            # If this isn't the last attempt, wait and retry
            if attempt < max_retries:
                missing_count = len(request_ids) - len(results)
                print(f"Still missing {missing_count} request IDs. Waiting {retry_delay} seconds before retry...")
                import time
                time.sleep(retry_delay)
                # Extend end time for next attempt
                end_time = datetime.utcnow()
        
        # Mark unfound requests as unknown (False)
        for request_id in request_ids:
            if request_id not in results:
                results[request_id] = False
                print(f"  Warning: Request ID {request_id} not found in CloudTrail after {max_retries + 1} attempts")
        
        return results
    
    def _is_cross_region(self, event: dict) -> bool:
        """Determine if a CloudTrail event represents a cross-region request.
        
        Args:
            event: CloudTrail event JSON
            
        Returns:
            True if request was cross-region, False otherwise
        """
        # Check for inference region in additionalEventData (ConverseStream specific)
        additional_data = event.get('additionalEventData', {})
        inference_region = additional_data.get('inferenceRegion', '')
        
        if inference_region and inference_region != self.home_region:
            return True
        
        # Check for inference profile ARN in request parameters
        request_params = event.get('requestParameters', {})
        inference_profile_arn = request_params.get('inferenceProfileArn', '')
        
        if inference_profile_arn:
            # Parse region from ARN: arn:aws:bedrock:REGION:...
            parts = inference_profile_arn.split(':')
            if len(parts) >= 4:
                request_region = parts[3]
                if request_region != self.home_region:
                    return True
        
        # Check event region vs home region
        event_region = event.get('awsRegion', '')
        if event_region and event_region != self.home_region:
            return True
        
        # Check for cross-region indicators in resources
        resources = event.get('resources', [])
        for resource in resources:
            arn = resource.get('ARN', '')
            if arn:
                parts = arn.split(':')
                if len(parts) >= 4:
                    resource_region = parts[3]
                    if resource_region != self.home_region:
                        return True
        
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Query CloudTrail for Bedrock request cross-region status'
    )
    parser.add_argument(
        '--request-ids',
        nargs='+',
        required=True,
        help='Bedrock request IDs to query'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--start-time',
        help='Start time (ISO format, default: 15 min ago)'
    )
    parser.add_argument(
        '--end-time',
        help='End time (ISO format, default: now)'
    )
    parser.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='Maximum retry attempts (default: 3)'
    )
    parser.add_argument(
        '--retry-delay',
        type=int,
        default=60,
        help='Delay between retries in seconds (default: 60)'
    )
    parser.add_argument(
        '--output',
        help='Output JSON file path'
    )
    
    args = parser.parse_args()
    
    # Parse times
    start_time = None
    end_time = None
    if args.start_time:
        start_time = datetime.fromisoformat(args.start_time)
    if args.end_time:
        end_time = datetime.fromisoformat(args.end_time)
    
    # Query CloudTrail
    querier = CloudTrailQuerier(region=args.region)
    results = querier.query_request_ids(
        request_ids=args.request_ids,
        start_time=start_time,
        end_time=end_time,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay
    )
    
    # Print results
    print("\nResults:")
    cross_region_count = sum(1 for is_cross in results.values() if is_cross)
    print(f"  Total requests: {len(results)}")
    print(f"  Cross-region: {cross_region_count}")
    print(f"  Same-region: {len(results) - cross_region_count}")
    
    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == '__main__':
    main()
