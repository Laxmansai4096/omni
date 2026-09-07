import requests
import time
import json

def test_pipeline():
    print("=== 1. Submitting test image to /api/v1/jobs/submit ===")
    with open('test_images/2_financial_table_matrix.png', 'rb') as f:
        resp = requests.post(
            'http://localhost:8000/api/v1/jobs/submit',
            files={'file': ('2_financial_table_matrix.png', f, 'image/png')}
        )

    print("HTTP Status:", resp.status_code)
    submit_data = resp.json()
    print("Submit Response:", json.dumps(submit_data, indent=2))
    job_id = submit_data['job_id']

    print(f"\n=== 2. Polling Job Lifecycle: {job_id} ===")
    for i in range(25):
        time.sleep(1)
        status_resp = requests.get(f'http://localhost:8000/api/v1/jobs/{job_id}/status').json()
        print(f"[{i+1:02d}s] Status: {status_resp.get('status')} | Stage: {status_resp.get('current_stage')} | Progress: {status_resp.get('progress_pct')}%")
        if status_resp.get('status') in ('COMPLETED', 'FAILED'):
            break

    if status_resp.get('status') == 'COMPLETED':
        print("\n=== 3. Fetching Completed Result ===")
        res = requests.get(f'http://localhost:8000/api/v1/jobs/{job_id}/result').json()
        total_elements = len(res.get('pages', [{}])[0].get('elements', []))
        summary = res.get('summary', {})
        print(f"SUCCESS! Total Elements Extracted: {total_elements}")
        print("Summary counts by category:", summary.get('counts_by_category'))
        print("Processing time ms:", summary.get('processing_time_ms'))
    else:
        print("Job did not complete:", status_resp)

if __name__ == '__main__':
    test_pipeline()
