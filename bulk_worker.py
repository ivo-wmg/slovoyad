"""
Slovoyad — Bulk Worker
Background queue processor for group evaluation.
Picks pending URLs, scrapes, evaluates, and saves results.
"""

import threading
import time
from utils import logger, extract_domain
from database import (
    get_next_pending_url, update_group_url_status,
    update_group_counters, get_group_url_retry_count,
    save_evaluation, get_connection,
)
from domains import get_domain_config, UnsupportedDomainError
from scraper import scrape_article, ScrapingError
from evaluator import ArticleEvaluator
from config import GEMINI_MODEL

QUEUE_DELAY = 10  # seconds between requests
MAX_RETRIES = 3

_worker_thread = None
_worker_lock = threading.Lock()


def start_worker():
    """Start the background bulk-processing thread if not already running."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return  # already running
        _worker_thread = threading.Thread(target=_process_queue, daemon=True)
        _worker_thread.start()
        logger.info('Bulk worker started')


def _process_queue():
    """Main worker loop: process pending URLs one by one."""
    while True:
        url_item = get_next_pending_url()
        if not url_item:
            logger.info('Bulk worker: queue empty, stopping')
            break

        url_id = url_item['id']
        group_id = url_item['group_id']
        url = url_item['url']

        # Mark as processing
        update_group_url_status(url_id, 'processing')

        # Update group status to running
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'UPDATE evaluation_groups SET status="running" WHERE id=%s AND status!="running"',
                    (group_id,),
                )
                conn.commit()
        finally:
            conn.close()

        try:
            logger.info(f'Bulk processing: {url}')

            # Extract domain
            domain = extract_domain(url)
            domain_config = get_domain_config(domain)

            # Scrape
            article_data = scrape_article(url)

            # Evaluate
            evaluator = ArticleEvaluator()
            evaluation = evaluator.evaluate(article_data, domain_config)

            # Save to DB
            eval_dict = evaluation.model_dump()
            version = save_evaluation(url, eval_dict)

            # Get the evaluation ID and link it to the group
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    from database import _url_hash
                    url_h = _url_hash(url)
                    cur.execute(
                        'SELECT id FROM evaluations WHERE url_hash=%s AND version=%s',
                        (url_h, version),
                    )
                    eval_row = cur.fetchone()
                    eval_id = eval_row['id'] if eval_row else None

                    # Update group_id on the evaluation
                    if eval_id:
                        cur.execute(
                            'UPDATE evaluations SET group_id=%s WHERE id=%s',
                            (group_id, eval_id),
                        )
                        conn.commit()
            finally:
                conn.close()

            # Mark URL as completed
            update_group_url_status(url_id, 'completed', evaluation_id=eval_id)
            logger.info(f'Bulk completed: {url} (score: {evaluation.final_overall_score})')

        except Exception as e:
            logger.error(f'Bulk error for {url}: {e}')
            retries = get_group_url_retry_count(url_id)
            if retries + 1 >= MAX_RETRIES:
                update_group_url_status(url_id, 'failed', error_message=str(e))
            else:
                update_group_url_status(url_id, 'pending', error_message=str(e))

        # Update group counters
        update_group_counters(group_id)

        # Wait before next request
        time.sleep(QUEUE_DELAY)

    logger.info('Bulk worker finished')
