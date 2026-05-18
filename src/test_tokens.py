#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование расхода токенов на этапе навигации по конфигурации 1С.
Сравнивает подходы: "без репозиторной карты" vs "с репозиторной картой".

Важно: тест измеряет только токены, которые LLM тратит на поиск и ориентацию
в конфигурации (поиск объектов, форм, модулей). Собственно решение задачи
(написание/исправление кода) требует примерно одинаковое количество токенов
в обоих случаях и в тест НЕ включается.
"""

import os
import re
import json
import random
from pathlib import Path
from collections import defaultdict
import tiktoken

# Конфигурация
CONFIG_PATH = Path(r"C:\Users\amak\Desktop\mis_2026-04-30")
REPO_MAP_PATH = Path(r"C:\Users\amak\Desktop\Задачи\2.Тест_поиск\repo_map")
RESULTS_PATH = Path(r"C:\Users\amak\Desktop\Задачи\2.Тест_поиск\test_results.json")

# Инициализация токенизатора (cl100k_base — используется GPT-4, GPT-3.5, Claude и др.)
ENCODER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    """Подсчитывает количество токенов в тексте."""
    if not text:
        return 0
    return len(ENCODER.encode(text))


def read_file_safe(path, max_chars=500_000):
    """Читает файл с ограничением размера."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_chars)
    except Exception:
        return ""


# =============================================================================
# Сценарии задач разработчика 1С
# =============================================================================

TEST_SCENARIOS = [
    {
        "id": 1,
        "name": "Документ Направление — не заполняется номенклатура в назначенных услугах",
        "description": "В документе Направление при заполнении табличной части НазначенныеУслуги "
                       "не подставляется НоменклатураМедицинскихУслуг из регистра CDAДокументыНазначенныхУслуг. "
                       "Нужно найти документ, его модуль объекта, связанные регистры и общие модули.",
        "keywords": ["Направление", "НазначенныеУслуги", "CDAДокументыНазначенныхУслуг", "модуль"],
        "target_objects": ["Documents/Направление", "InformationRegisters/CDAДокументыНазначенныхУслуг"],
    },
    {
        "id": 2,
        "name": "Справочник Сотрудники — добавить реквизит для хранения идентификатора ФРМР",
        "description": "В справочнике Сотрудники нужно добавить реквизит ИдентификаторФРМР "
                       "с типом Строка и разместить на форме элемента после поля КодПоОМС. "
                       "Требуется найти справочник, его форму, модули, связанные общие модули.",
        "keywords": ["Сотрудники", "ИдентификаторФРМР", "ФРМР", "форма"],
        "target_objects": ["Catalogs/Сотрудники"],
    },
    {
        "id": 3,
        "name": "DICOMWorkList — не подставляется ScheduledProcedureStepID при формировании Worklist",
        "description": "В модуле DICOMWorkList при формировании Worklist для аппарата МРТ "
                       "не подставляется ScheduledProcedureStepID из регистра DicomWorkList. "
                       "Требуется найти общие модули DICOM, регистр DicomWorkList, связанные обработки.",
        "keywords": ["DICOMWorkList", "DicomWorkList", "ScheduledProcedureStepID", "модуль"],
        "target_objects": ["CommonModules/DICOMWorkList", "InformationRegisters/DicomWorkList"],
    },
    {
        "id": 4,
        "name": "Документ ВыпискаИзСтационара — не формируется CDA при проведении",
        "description": "В документе ВыпискаИзСтационара при проведении не формируется запись "
                       "в регистре CDAДокументыМедицинскогоДокумента. Нужно найти документ, "
                       "его модуль объекта, регистр и связанные модули формирования CDA.",
        "keywords": ["ВыпискаИзСтационара", "CDA", "CDAДокументыМедицинскогоДокумента", "модуль"],
        "target_objects": ["Documents/ВыпискаИзСтационара", "InformationRegisters/CDAДокументыМедицинскогоДокумента"],
    },
    {
        "id": 5,
        "name": "HL7 — при получении сообщения ADT^A08 не обновляются данные пациента",
        "description": "При получении HL7-сообщения типа ADT^A08 не обновляются данные пациента "
                       "в справочнике Пациенты. Требуется найти обработки HL7, общие модули HL7, "
                       "подписки на события и связанные HTTP-сервисы.",
        "keywords": ["HL7", "ADT^A08", "Пациенты", "обработка"],
        "target_objects": ["CommonModules/HL7ПодпискиНаСобытия"],
    },
]


# =============================================================================
# Подход 1: БЕЗ репозиторной карты (наивный поиск)
# =============================================================================

class NaiveApproach:
    """Симулирует наивный подход разработчика/ИИ без карты."""

    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.all_files = []
        self._index_files()

    def _index_files(self):
        """Индексирует все релевантные файлы конфигурации."""
        for ext in [".bsl", ".xml"]:
            for f in self.config_path.rglob(f"*{ext}"):
                # Исключаем бинарные и очень большие файлы
                if f.stat().st_size < 5_000_000:  # < 5 MB
                    self.all_files.append(f)

    def search_files(self, keywords, max_results=50):
        """Ищет файлы по ключевым словам (простой поиск по именам)."""
        results = []
        keyword_patterns = [re.compile(k, re.IGNORECASE) for k in keywords]

        for f in self.all_files:
            name_lower = f.name.lower()
            path_lower = str(f).lower()
            for pat in keyword_patterns:
                if pat.search(name_lower) or pat.search(path_lower):
                    results.append(f)
                    break
            if len(results) >= max_results:
                break

        return results

    def simulate_task(self, scenario):
        """Симулирует решение задачи без карты."""
        # Шаг 1: Поиск файлов по ключевым словам
        found_files = self.search_files(scenario["keywords"], max_results=50)

        # Шаг 2: Если мало результатов, расширяем поиск
        if len(found_files) < 10:
            # Ищем по связанным словам
            extra_keywords = ["модуль", "form", "module", "register", "регистр"]
            found_files += self.search_files(extra_keywords, max_results=30)

        # Шаг 3: Читаем найденные файлы
        contents = []
        for f in found_files[:40]:  # ограничиваем, но без карты ИИ может прочитать много
            contents.append(f"=== {f.relative_to(self.config_path)} ===\n")
            contents.append(read_file_safe(f, max_chars=50_000))
            contents.append("\n\n")

        # Шаг 4: Также читаем некоторые общие модули (ИИ часто лезет в них)
        common_modules = list(self.config_path.glob("CommonModules/*/*/Module.bsl"))
        random.shuffle(common_modules)
        for f in common_modules[:10]:
            contents.append(f"=== {f.relative_to(self.config_path)} ===\n")
            contents.append(read_file_safe(f, max_chars=20_000))
            contents.append("\n\n")

        full_text = "\n".join(contents)
        return {
            "files_read": len(found_files) + 10,
            "text": full_text,
            "tokens": count_tokens(full_text),
        }


# =============================================================================
# Подход 2: С репозиторной картой
# =============================================================================

class RepoMapApproach:
    """Симулирует подход с использованием репозиторной карты."""

    def __init__(self, config_path, repo_map_path):
        self.config_path = Path(config_path)
        self.repo_map_path = Path(repo_map_path)
        self.map_files = list(self.repo_map_path.glob("*.md"))
        self.map_index = {}
        self._build_index()

    def _build_index(self):
        """Строит индекс по содержимому карт."""
        for mf in self.map_files:
            content = read_file_safe(mf)
            self.map_index[mf.name] = content

    def _find_relevant_maps(self, keywords):
        """Находит релевантные файлы карт по ключевым словам."""
        relevant = []
        keyword_patterns = [re.compile(k, re.IGNORECASE) for k in keywords]

        for name, content in self.map_index.items():
            for pat in keyword_patterns:
                if pat.search(content):
                    relevant.append(name)
                    break

        return relevant

    def _find_objects_in_map(self, keywords):
        """Ищет конкретные объекты в картах по ключевым словам."""
        matches = []
        for name, content in self.map_index.items():
            lines = content.splitlines()
            for line in lines:
                for kw in keywords:
                    if kw.lower() in line.lower():
                        # Извлекаем имя объекта из заголовка
                        m = re.match(r'^##+\s+(.+)$', line.strip())
                        if m:
                            matches.append(m.group(1).strip())
                        else:
                            matches.append(line.strip()[:80])
                        break
        return list(set(matches))[:20]

    def _read_target_files(self, target_objects, max_files=8):
        """Читает только целевые файлы из конфигурации."""
        contents = []
        files_read = 0

        for obj_path in target_objects:
            base = self.config_path / obj_path
            if not base.exists():
                continue
            # Находим ключевые файлы: модули и формы
            for pattern in ["**/*.bsl", "**/*Module*.xml", "**/Ext/Help.xml"]:
                for f in base.glob(pattern):
                    if files_read >= max_files:
                        break
                    contents.append(f"=== {f.relative_to(self.config_path)} ===\n")
                    contents.append(read_file_safe(f, max_chars=30_000))
                    contents.append("\n\n")
                    files_read += 1

        return "\n".join(contents), files_read

    def simulate_task(self, scenario):
        """Симулирует решение задачи с картой."""
        # Шаг 1: Читаем README карты (всегда)
        steps_text = []
        steps_text.append("=== РЕПОЗИТОРНАЯ КАРТА ===\n")
        steps_text.append(self.map_index.get("README.md", ""))
        steps_text.append("\n\n")

        # Шаг 2: Находим релевантные карты
        relevant_maps = self._find_relevant_maps(scenario["keywords"])
        for map_name in relevant_maps[:3]:
            steps_text.append(f"=== {map_name} ===\n")
            steps_text.append(self.map_index.get(map_name, "")[:20_000])  # обрезаем
            steps_text.append("\n\n")

        # Шаг 3: Ищем конкретные объекты в индексе
        obj_matches = self._find_objects_in_map(scenario["keywords"])
        if obj_matches:
            steps_text.append("=== НАЙДЕННЫЕ ОБЪЕКТЫ ===\n")
            for m in obj_matches:
                steps_text.append(f"- {m}\n")
            steps_text.append("\n\n")

        # Шаг 4: Читаем только нужные файлы из конфигурации
        target_text, files_read = self._read_target_files(scenario.get("target_objects", []), max_files=6)
        steps_text.append(target_text)

        full_text = "".join(steps_text)
        return {
            "maps_read": 1 + len(relevant_maps[:3]),
            "files_read": files_read,
            "text": full_text,
            "tokens": count_tokens(full_text),
        }


# =============================================================================
# Запуск тестов
# =============================================================================

def run_tests():
    print("=" * 70)
    print("ТЕСТИРОВАНИЕ РАСХОДА ТОКЕНОВ: БЕЗ КАРТЫ vs С КАРТОЙ")
    print("=" * 70)
    print(f"Конфигурация: {CONFIG_PATH}")
    print(f"Репозиторная карта: {REPO_MAP_PATH}")
    print()

    naive = NaiveApproach(CONFIG_PATH)
    repo_map = RepoMapApproach(CONFIG_PATH, REPO_MAP_PATH)

    results = []

    for scenario in TEST_SCENARIOS:
        print(f"\n{'─' * 70}")
        print(f"Сценарий #{scenario['id']}: {scenario['name']}")
        print(f"Описание: {scenario['description']}")
        print(f"Ключевые слова: {', '.join(scenario['keywords'])}")
        print()

        # Без карты
        print("[БЕЗ КАРТЫ] Симуляция...")
        naive_result = naive.simulate_task(scenario)
        print(f"  Прочитано файлов: {naive_result['files_read']}")
        print(f"  Символов текста: {len(naive_result['text']):,}")
        print(f"  Токенов: {naive_result['tokens']:,}")

        # С картой
        print("[С КАРТОЙ] Симуляция...")
        repo_result = repo_map.simulate_task(scenario)
        print(f"  Прочитано карт: {repo_result['maps_read']}")
        print(f"  Прочитано файлов: {repo_result['files_read']}")
        print(f"  Символов текста: {len(repo_result['text']):,}")
        print(f"  Токенов: {repo_result['tokens']:,}")

        # Экономия
        saving = naive_result['tokens'] - repo_result['tokens']
        saving_pct = (saving / naive_result['tokens'] * 100) if naive_result['tokens'] > 0 else 0
        print(f"\n>>> ЭКОНОМИЯ: {saving:,} токенов ({saving_pct:.1f}%)")

        results.append({
            "scenario": scenario,
            "naive": {
                "files_read": naive_result['files_read'],
                "chars": len(naive_result['text']),
                "tokens": naive_result['tokens'],
            },
            "repo_map": {
                "maps_read": repo_result['maps_read'],
                "files_read": repo_result['files_read'],
                "chars": len(repo_result['text']),
                "tokens": repo_result['tokens'],
            },
            "saving_tokens": saving,
            "saving_percent": round(saving_pct, 2),
        })

    # Итоги
    print(f"\n{'=' * 70}")
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print(f"{'=' * 70}")

    total_naive = sum(r["naive"]["tokens"] for r in results)
    total_repo = sum(r["repo_map"]["tokens"] for r in results)
    total_saving = total_naive - total_repo
    total_saving_pct = (total_saving / total_naive * 100) if total_naive > 0 else 0

    print(f"\nОбщий расход токенов на навигацию БЕЗ карты: {total_naive:,}")
    print(f"Общий расход токенов на навигацию С картой:   {total_repo:,}")
    print(f"Общая экономия на навигацию:                  {total_saving:,} токенов ({total_saving_pct:.1f}%)")
    print(f"\nСредняя экономия на навигацию по задаче:      {total_saving / len(results):,.0f} токенов")
    print(f"\n⚠️  Важно: это только токены на поиск/ориентацию. Токены на собственно решение задачи")
    print(f"   (генерацию кода) не измеряются и примерно одинаковы в обоих случаях.")

    # Сохраняем результаты
    summary = {
        "total_naive_tokens": total_naive,
        "total_repo_tokens": total_repo,
        "total_saving_tokens": total_saving,
        "total_saving_percent": round(total_saving_pct, 2),
        "scenarios": results,
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nРезультаты сохранены в: {RESULTS_PATH}")

    return summary


if __name__ == "__main__":
    run_tests()
