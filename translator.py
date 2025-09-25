import os
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from deep_translator import GoogleTranslator, MyMemoryTranslator

import cache_manager


def bilingual_format(orig, trans):
    """Định dạng song ngữ"""
    return f"<i><font color='#B0B0B0'>{orig}</font></i>\n<b><font color='#FFFFFF'>{trans}</font></b>"

def safe_translate(text, dest_lang, retries=3):
    """Google chính, fallback MyMemory"""
    last_err = None
    for attempt in range(retries):
        try:
            return GoogleTranslator(source="auto", target=dest_lang).translate(text)
        except Exception as e:
            last_err = e
            time.sleep(1.2 * (attempt + 1))
    # fallback MyMemory
    try:
        return MyMemoryTranslator(source="auto", target=dest_lang).translate(text)
    except Exception:
        return text  # giữ nguyên nếu thất bại

def translate_chunk(texts, dest_lang, cache, stop_event, pause_event, retries=3):
    results = []
    for text in texts:
        if stop_event and stop_event():
            break
        if pause_event and pause_event.is_set():
            while pause_event.is_set():
                time.sleep(0.2)

        # cache lookup
        if cache.get(dest_lang) and text in cache[dest_lang]:
            results.append(cache[dest_lang][text])
            continue

        translated = safe_translate(text, dest_lang, retries)
        cache.setdefault(dest_lang, {})[text] = translated
        results.append(translated)
    return results

def read_subtitle_file(path, encoding="utf-8"):
    with open(path, "r", encoding=encoding, errors="ignore") as f:
        lines = f.readlines()
    ext = os.path.splitext(path)[1].lower()
    return lines, ("vtt" if ext == ".vtt" else "srt")

def write_subtitle_file(output_path, original_lines, results_map, encoding="utf-8"):
    with open(output_path, "w", encoding=encoding, errors="ignore") as f:
        for idx, line in enumerate(original_lines):
            if idx in results_map:
                f.write(results_map[idx] + "\n")
            else:
                f.write(line)

def translate_srt_file(path, cache, dest_lang="vi", output_mode="bilingual",
                       chunk_size=10, max_workers=3, min_sleep=0.25,
                       max_sleep=0.6, stop_event=None, pause_event=None,
                       progress_callback=None, encoding="utf-8",
                       save_choice=1, output_folder=None, retries=4):
    """Dịch 1 file SRT/VTT"""
    lines, ftype = read_subtitle_file(path, encoding=encoding)

    # lấy text để dịch
    text_lines = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.isdigit() or "-->" in s:
            continue
        if ftype == "vtt" and i == 0 and s.upper().startswith("WEBVTT"):
            continue
        text_lines.append((i, line.rstrip("\n")))

    if not text_lines:
        return None

    indices = [idx for idx, _ in text_lines]
    texts = [txt for _, txt in text_lines]
    chunks = [texts[i:i + chunk_size] for i in range(0, len(texts), chunk_size)]
    index_chunks = [indices[i:i + chunk_size] for i in range(0, len(indices), chunk_size)]

    total_chunks = len(chunks)
    results_map = {}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_idx = {
            ex.submit(translate_chunk, chunk, dest_lang, cache, stop_event, pause_event, retries): ci
            for ci, chunk in enumerate(chunks)
        }
        done_cnt = 0
        for future in as_completed(future_to_idx):
            if stop_event and stop_event():
                break
            ci = future_to_idx[future]
            try:
                translated_list = future.result()
            except Exception:
                translated_list = chunks[ci]  # fallback giữ nguyên

            for local_i, trans_text in enumerate(translated_list):
                line_idx = index_chunks[ci][local_i]
                orig_text = texts[ci * chunk_size + local_i]
                if output_mode == "bilingual":
                    if orig_text.strip().lower() == trans_text.strip().lower():
                        results_map[line_idx] = trans_text
                    else:
                        results_map[line_idx] = bilingual_format(orig_text, trans_text)
                else:
                    results_map[line_idx] = trans_text

            done_cnt += 1
            if progress_callback:
                progress_callback(done_cnt, total_chunks)
            time.sleep(random.uniform(min_sleep, max_sleep))

    base_name = os.path.splitext(os.path.basename(path))[0]
    ext = ".vtt" if ftype == "vtt" else ".srt"
    out_name = f"{base_name}_{output_mode}{ext}"

    if save_choice == 2 and output_folder:
        os.makedirs(output_folder, exist_ok=True)
        output_path = os.path.join(output_folder, out_name)
    else:
        output_path = os.path.join(os.path.dirname(path), out_name)

    write_subtitle_file(output_path, lines, results_map, encoding=encoding)

    try:
        cache_manager.save_cache(cache)
    except Exception as e:
        print(f"[WARN] Failed to save cache: {e}")

    return output_path

def translate_srt_files(files, **kwargs):
    outputs = []
    for f in files:
        outp = translate_srt_file(f, **kwargs)
        if outp:
            outputs.append(outp)
    return outputs
