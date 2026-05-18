#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор репозиторных карт для конфигураций 1С.
Создает сжатую навигационную структуру, позволяющую LLM ориентироваться
в конфигурации без необходимости чтения всех файлов.
"""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
import argparse

# Путь к конфигурации по умолчанию
DEFAULT_CONFIG_PATH = r"C:\Users\amak\Desktop\mis_2026-04-30"
# Путь для сохранения карт
DEFAULT_OUTPUT_PATH = r"C:\Users\amak\Desktop\Задачи\2.Тест_поиск\repo_map"

# Типы объектов метаданных 1С и их человекочитаемые названия
OBJECT_TYPES = {
    "Catalog": "Справочники",
    "Document": "Документы",
    "InformationRegister": "РегистрыСведений",
    "AccumulationRegister": "РегистрыНакопления",
    "CommonModule": "ОбщиеМодули",
    "DataProcessor": "Обработки",
    "Report": "Отчеты",
    "ChartOfCharacteristicTypes": "ПланыВидовХарактеристик",
    "ChartOfAccounts": "ПланыСчетов",
    "ChartOfCalculationTypes": "ПланыВидовРасчета",
    "BusinessProcess": "БизнесПроцессы",
    "Task": "Задачи",
    "Enum": "Перечисления",
    "ExchangePlan": "ПланыОбмена",
    "FilterCriterion": "КритерииОтбора",
    "SettingsStorage": "ХранилищаНастроек",
    "CommonAttribute": "ОбщиеРеквизиты",
    "CommonPicture": "ОбщиеКартинки",
    "CommonTemplate": "ОбщиеМакеты",
    "CommonForm": "ОбщиеФормы",
    "CommonCommand": "ОбщиеКоманды",
    "Role": "Роли",
    "SessionParameter": "ПараметрыСеанса",
    "ScheduledJob": "РегламентныеЗадания",
    "DefinedType": "ОпределяемыеТипы",
    "ExternalDataSource": "ВнешниеИсточникиДанных",
    "Subsystem": "Подсистемы",
    "DocumentJournal": "ЖурналыДокументов",
    "EventSubscription": "ПодпискиНаСобытия",
    "FunctionalOption": "ФункциональныеОпции",
    "FunctionalOptionsParameter": "ПараметрыФункциональныхОпций",
    "WSReference": "WSСсылки",
    "XDTOPackage": "XDTOПакеты",
    "WebService": "WebСервисы",
    "HTTPService": "HTTPСервисы",
}

# Папки в файловой системе, соответствующие типам
FOLDER_MAP = {
    "Catalog": "Catalogs",
    "Document": "Documents",
    "InformationRegister": "InformationRegisters",
    "AccumulationRegister": "AccumulationRegisters",
    "CommonModule": "CommonModules",
    "DataProcessor": "DataProcessors",
    "Report": "Reports",
    "ChartOfCharacteristicTypes": "ChartsOfCharacteristicTypes",
    "ChartOfAccounts": "ChartsOfAccounts",
    "ChartOfCalculationTypes": "ChartsOfCalculationTypes",
    "BusinessProcess": "BusinessProcesses",
    "Task": "Tasks",
    "Enum": "Enums",
    "ExchangePlan": "ExchangePlans",
    "SettingsStorage": "SettingsStorages",
    "CommonPicture": "CommonPictures",
    "CommonTemplate": "CommonTemplates",
    "CommonForm": "CommonForms",
    "CommonCommand": "CommonCommands",
    "Role": "Roles",
    "ScheduledJob": "ScheduledJobs",
    "ExternalDataSource": "ExternalDataSources",
    "Subsystem": "Subsystems",
    "DocumentJournal": "DocumentJournals",
    "EventSubscription": "EventSubscriptions",
    "WebService": "WebServices",
    "HTTPService": "HTTPServices",
    "XDTOPackage": "XDTOPackages",
}


def parse_config_dump_info(config_path):
    """Парсит ConfigDumpInfo.xml и возвращает структуру метаданных."""
    dump_path = Path(config_path) / "ConfigDumpInfo.xml"
    if not dump_path.exists():
        print(f"ConfigDumpInfo.xml не найден по пути: {dump_path}")
        return {}

    tree = ET.parse(dump_path)
    root = tree.getroot()

    # Пространство имен
    ns = {"": "http://v8.1c.ru/8.3/xcf/dumpinfo"}

    objects = defaultdict(lambda: defaultdict(dict))
    # objects[type][name] = {properties}

    for meta in root.findall(".//{http://v8.1c.ru/8.3/xcf/dumpinfo}Metadata", ns):
        name_attr = meta.get("name", "")
        if not name_attr or "." not in name_attr:
            continue

        parts = name_attr.split(".", 1)
        obj_type = parts[0]
        obj_path = parts[1]

        # Основной объект (не подэлемент)
        if "." not in obj_path:
            objects[obj_type][obj_path]["_id"] = meta.get("id", "")
            # Извлекаем вложенные элементы (реквизиты, измерения, ресурсы)
            for child in meta:
                child_name = child.get("name", "")
                if child_name and "." in child_name:
                    sub_parts = child_name.split(".")
                    if len(sub_parts) >= 3:
                        element_type = sub_parts[1]  # Attribute, Dimension, Resource и т.д.
                        element_name = sub_parts[2]
                        if "elements" not in objects[obj_type][obj_path]:
                            objects[obj_type][obj_path]["elements"] = []
                        objects[obj_type][obj_path]["elements"].append({
                            "type": element_type,
                            "name": element_name,
                            "id": child.get("id", "")
                        })
        else:
            # Это подэлемент (модуль, форма, справка)
            obj_name = obj_path.split(".")[0]
            sub_type = obj_path.split(".", 1)[1] if "." in obj_path else ""
            if obj_name in objects[obj_type]:
                if "sub_elements" not in objects[obj_type][obj_name]:
                    objects[obj_type][obj_name]["sub_elements"] = []
                objects[obj_type][obj_name]["sub_elements"].append(sub_type)

    return dict(objects)


def scan_file_system(config_path):
    """Сканирует файловую систему и собирает структуру модулей, форм и т.д."""
    base = Path(config_path)
    fs_structure = defaultdict(lambda: defaultdict(dict))

    for type_key, folder in FOLDER_MAP.items():
        folder_path = base / folder
        if not folder_path.exists():
            continue

        for obj_dir in folder_path.iterdir():
            if not obj_dir.is_dir():
                continue
            obj_name = obj_dir.name
            fs_structure[type_key][obj_name]["forms"] = []
            fs_structure[type_key][obj_name]["modules"] = []
            fs_structure[type_key][obj_name]["commands"] = []
            fs_structure[type_key][obj_name]["templates"] = []

            # Формы
            forms_dir = obj_dir / "Forms"
            if forms_dir.exists():
                for form_dir in forms_dir.iterdir():
                    if form_dir.is_dir():
                        fs_structure[type_key][obj_name]["forms"].append(form_dir.name)

            # Модули
            ext_dir = obj_dir / "Ext"
            if ext_dir.exists():
                for f in ext_dir.iterdir():
                    if f.is_file() and f.suffix.lower() == ".bsl":
                        fs_structure[type_key][obj_name]["modules"].append(f.name)

            # Команды
            commands_dir = obj_dir / "Commands"
            if commands_dir.exists():
                for cmd_dir in commands_dir.iterdir():
                    if cmd_dir.is_dir():
                        cmd_module = cmd_dir / "Ext" / "CommandModule.bsl"
                        if cmd_module.exists():
                            fs_structure[type_key][obj_name]["commands"].append(cmd_dir.name)

            # Макеты
            templates_dir = obj_dir / "Templates"
            if templates_dir.exists():
                for tmpl_dir in templates_dir.iterdir():
                    if tmpl_dir.is_dir():
                        fs_structure[type_key][obj_name]["templates"].append(tmpl_dir.name)

    # Общие модули — особая структура
    cm_folder = base / "CommonModules"
    if cm_folder.exists():
        for obj_dir in cm_folder.iterdir():
            if not obj_dir.is_dir():
                continue
            obj_name = obj_dir.name
            fs_structure["CommonModule"][obj_name]["modules"] = []
            ext_dir = obj_dir / "Ext"
            if ext_dir.exists():
                for f in ext_dir.iterdir():
                    if f.is_file() and f.suffix.lower() == ".bsl":
                        fs_structure["CommonModule"][obj_name]["modules"].append(f.name)

    # HTTP сервисы — модули
    http_folder = base / "HTTPServices"
    if http_folder.exists():
        for obj_dir in http_folder.iterdir():
            if not obj_dir.is_dir():
                continue
            obj_name = obj_dir.name
            fs_structure["HTTPService"][obj_name]["modules"] = []
            for f in (obj_dir / "Ext").iterdir() if (obj_dir / "Ext").exists() else []:
                if f.is_file() and f.suffix.lower() == ".bsl":
                    fs_structure["HTTPService"][obj_name]["modules"].append(f.name)

    # Web сервисы — модули
    ws_folder = base / "WebServices"
    if ws_folder.exists():
        for obj_dir in ws_folder.iterdir():
            if not obj_dir.is_dir():
                continue
            obj_name = obj_dir.name
            fs_structure["WebService"][obj_name]["modules"] = []
            for f in (obj_dir / "Ext").iterdir() if (obj_dir / "Ext").exists() else []:
                if f.is_file() and f.suffix.lower() == ".bsl":
                    fs_structure["WebService"][obj_name]["modules"].append(f.name)

    return dict(fs_structure)


def analyze_bsl_module(file_path, obj_type, obj_name):
    """Анализирует .bsl модуль: извлекает процедуры/функции и вызовы."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"procedures": [], "calls": []}

    # Находим процедуры и функции
    proc_pattern = re.compile(
        r'^(\s*)(Процедура|Функция|procedure|function)\s+([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)\s*\(',
        re.MULTILINE | re.IGNORECASE
    )
    procedures = [m.group(3) for m in proc_pattern.finditer(content)]

    # Находим вызовы общих модулей (Шаблон: ИмяМодуля.Процедура или ОбщийМодуль.ИмяМодуля)
    # Примеры: ОбщегоНазначения.СообщитьПользователю, РаботаСДатами.РазностьДат
    call_pattern = re.compile(
        r'(?<![А-Яа-яA-Za-z0-9_])([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*?)\.([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)\s*\(',
        re.MULTILINE
    )
    calls = []
    for m in call_pattern.finditer(content):
        module = m.group(1)
        method = m.group(2)
        calls.append({"module": module, "method": method})

    # Уникальные вызванные модули
    unique_modules = sorted(set(c["module"] for c in calls))

    return {
        "procedures": procedures[:20],  # ограничиваем для краткости
        "calls": unique_modules[:15],
        "size_lines": len(content.splitlines()),
        "size_chars": len(content)
    }


def build_module_graph(config_path, fs_structure, max_files=500):
    """Строит граф зависимостей модулей (ограниченное число файлов)."""
    base = Path(config_path)
    graph = defaultdict(set)
    module_info = {}
    files_analyzed = 0

    for obj_type, objects in fs_structure.items():
        for obj_name, info in objects.items():
            if files_analyzed >= max_files:
                break
            folder = FOLDER_MAP.get(obj_type, obj_type + "s")
            for mod_name in info.get("modules", []):
                if files_analyzed >= max_files:
                    break
                if obj_type == "CommonModule":
                    mod_path = base / folder / obj_name / "Ext" / mod_name
                elif obj_type in ["HTTPService", "WebService"]:
                    mod_path = base / folder / obj_name / "Ext" / mod_name
                else:
                    mod_path = base / folder / obj_name / "Ext" / mod_name

                if mod_path.exists():
                    analysis = analyze_bsl_module(mod_path, obj_type, obj_name)
                    module_info[f"{obj_type}.{obj_name}"] = analysis
                    for called in analysis["calls"]:
                        graph[obj_name].add(called)
                    files_analyzed += 1

    # Преобразуем set в sorted list
    graph_dict = {k: sorted(v) for k, v in graph.items()}
    return graph_dict, module_info


def parse_subsystem_xml(xml_path, parent_name=""):
    """Рекурсивно парсит XML подсистемы."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception:
        return None

    # Имя подсистемы
    name = ""
    for elem in root.iter():
        if elem.tag.endswith("}Name") and elem.text:
            name = elem.text
            break

    if not name:
        return None

    full_name = f"{parent_name}.{name}" if parent_name else name
    sub_info = {
        "name": name,
        "full_name": full_name,
        "objects": [],
        "subsystems": []
    }

    # Состав подсистемы (входящие объекты)
    for elem in root.iter():
        if elem.tag.endswith("}Content"):
            for item in elem:
                text = item.text
                if text and "." in text:
                    sub_info["objects"].append(text)
        elif elem.tag.endswith("}Subsystems"):
            for sub in elem:
                if sub.text:
                    sub_name = sub.text.split(".")[-1] if "." in sub.text else sub.text
                    # Ищем XML в подпапке Subsystems родительской папки
                    sub_xml = xml_path.parent / "Subsystems" / f"{sub_name}.xml"
                    if sub_xml.exists():
                        child = parse_subsystem_xml(sub_xml, full_name)
                        if child:
                            sub_info["subsystems"].append(child)

    return sub_info


def parse_subsystems(config_path, fs_structure):
    """Парсит подсистемы и собирает входящие в них объекты."""
    base = Path(config_path)
    subsystems_dir = base / "Subsystems"
    if not subsystems_dir.exists():
        return {}

    subsystems = {}

    # 1. Читаем корневые подсистемы из Configuration.xml
    config_xml = base / "Configuration.xml"
    root_subsystem_names = []
    if config_xml.exists():
        try:
            content = config_xml.read_text(encoding="utf-8")
            # Ищем <Subsystem>Имя</Subsystem>
            for m in re.finditer(r'<Subsystem>([^<]+)</Subsystem>', content):
                root_subsystem_names.append(m.group(1))
        except Exception as e:
            print(f"      Ошибка чтения Configuration.xml: {e}")

    # 2. Для каждой корневой подсистемы ищем XML в файловой системе
    for sub_name in root_subsystem_names:
        sub_dir = subsystems_dir / sub_name
        if not sub_dir.exists():
            continue

        # Корневая подсистема описана в Configuration.xml, но у неё может быть CommandInterface
        # и подчиненные подсистемы в папке Subsystems
        sub_info = {
            "name": sub_name,
            "full_name": sub_name,
            "objects": [],
            "subsystems": []
        }

        # Ищем подчиненные подсистемы
        child_subsystems_dir = sub_dir / "Subsystems"
        if child_subsystems_dir.exists():
            for child_xml in child_subsystems_dir.glob("*.xml"):
                child = parse_subsystem_xml(child_xml, sub_name)
                if child:
                    sub_info["subsystems"].append(child)
                    # Добавляем объекты дочерней подсистемы в родительскую для полноты
                    sub_info["objects"].extend(child.get("objects", []))

        subsystems[sub_name] = sub_info

    return subsystems


def generate_readme(config_path, objects, output_path):
    """Генерирует README.md с общей статистикой."""
    lines = [
        "# Репозиторная карта конфигурации 1С",
        "",
        f"**Конфигурация:** 1С:Здравоохранение72",
        f"**Версия:** 2.0.8.2",
        f"**Путь:** `{config_path}`",
        "",
        "## Статистика объектов",
        "",
        "| Тип объекта | Количество |",
        "|-------------|------------|",
    ]

    total = 0
    for obj_type, items in sorted(objects.items(), key=lambda x: -len(x[1])):
        count = len(items)
        total += count
        ru_name = OBJECT_TYPES.get(obj_type, obj_type)
        lines.append(f"| {ru_name} ({obj_type}) | {count} |")

    lines.append(f"| **Итого** | **{total}** |")
    lines.append("")
    lines.append("## Навигация по картам")
    lines.append("")
    lines.append("- [Индекс объектов](objects_index.md) — алфавитный список всех объектов")
    lines.append("- [Подсистемы](subsystems.md) — иерархия подсистем и входящие объекты")
    lines.append("- [Граф модулей](modules_graph.md) — зависимости общих модулей")
    lines.append("- [Справочники](Catalogs.md) — карта справочников")
    lines.append("- [Документы](Documents.md) — карта документов")
    lines.append("- [Регистры сведений](InformationRegisters.md) — карта регистров сведений")
    lines.append("- [Общие модули](CommonModules.md) — карта общих модулей")
    lines.append("- [Обработки](DataProcessors.md) — карта обработок")
    lines.append("")
    lines.append("## Принцип работы с картой")
    lines.append("")
    lines.append("1. Определите, к какой подсистеме относится задача — [subsystems.md](subsystems.md)")
    lines.append("2. Найдите объект в индексе — [objects_index.md](objects_index.md)")
    lines.append("3. Изучите структуру объекта в соответствующей карте (Catalogs.md, Documents.md и т.д.)")
    lines.append("4. При необходимости изучите зависимости в [modules_graph.md](modules_graph.md)")
    lines.append("5. Переходите к чтению только нужных .bsl и .xml файлов")
    lines.append("")

    readme_path = Path(output_path) / "README.md"
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Создан: {readme_path}")


def generate_objects_index(objects, fs_structure, output_path):
    """Генерирует алфавитный индекс всех объектов."""
    lines = [
        "# Индекс объектов метаданных",
        "",
        "Алфавитный список всех объектов конфигурации.",
        "",
    ]

    # Собираем все объекты в один список
    all_objects = []
    for obj_type, items in objects.items():
        for obj_name, obj_data in items.items():
            all_objects.append({
                "type": obj_type,
                "name": obj_name,
                "ru_type": OBJECT_TYPES.get(obj_type, obj_type),
                "elements_count": len(obj_data.get("elements", [])),
                "forms_count": len(fs_structure.get(obj_type, {}).get(obj_name, {}).get("forms", [])),
                "modules_count": len(fs_structure.get(obj_type, {}).get(obj_name, {}).get("modules", [])),
            })

    all_objects.sort(key=lambda x: x["name"].lower())

    # Группировка по первой букве
    current_letter = ""
    for obj in all_objects:
        first_letter = obj["name"][0].upper() if obj["name"] else "#"
        if first_letter != current_letter:
            current_letter = first_letter
            lines.append(f"\n## {current_letter}\n")

        extra = []
        if obj["elements_count"]:
            extra.append(f"{obj['elements_count']} рекв.")
        if obj["forms_count"]:
            extra.append(f"{obj['forms_count']} форм")
        if obj["modules_count"]:
            extra.append(f"{obj['modules_count']} мод.")

        extra_str = f" — ({', '.join(extra)})" if extra else ""
        lines.append(f"- **{obj['name']}** ({obj['ru_type']}){extra_str}")

    index_path = Path(output_path) / "objects_index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Создан: {index_path}")


def generate_subsystems_map(subsystems, output_path):
    """Генерирует карту подсистем."""
    lines = [
        "# Подсистемы конфигурации",
        "",
        "Иерархия подсистем и входящие в них объекты.",
        "",
    ]

    def write_subsystem(sub, level=0):
        indent = "  " * level
        lines.append(f"{indent}- ## {sub['full_name']}\n")

        # Группируем объекты по типу
        by_type = defaultdict(list)
        for obj_ref in sub.get("objects", []):
            parts = obj_ref.split(".", 1)
            obj_type = parts[0] if len(parts) > 0 else "Unknown"
            obj_name = parts[1] if len(parts) > 1 else obj_ref
            by_type[obj_type].append(obj_name)

        if by_type:
            lines.append(f"{indent}  **Состав:**\n")
            for obj_type, names in sorted(by_type.items()):
                ru_type = OBJECT_TYPES.get(obj_type, obj_type)
                display_names = names[:20]
                suffix = f" и еще {len(names) - 20}" if len(names) > 20 else ""
                lines.append(f"{indent}  - {ru_type}: {', '.join(display_names)}{suffix}")
            lines.append("")

        for child in sub.get("subsystems", []):
            write_subsystem(child, level + 1)

    for name, sub in sorted(subsystems.items()):
        write_subsystem(sub)

    sub_path = Path(output_path) / "subsystems.md"
    sub_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Создан: {sub_path}")


def generate_type_map(obj_type, objects, fs_structure, output_path):
    """Генерирует карту для конкретного типа объектов."""
    ru_name = OBJECT_TYPES.get(obj_type, obj_type)
    filename = f"{obj_type}s.md"
    if obj_type == "InformationRegister":
        filename = "InformationRegisters.md"
    elif obj_type == "AccumulationRegister":
        filename = "AccumulationRegisters.md"

    lines = [
        f"# {ru_name}",
        f"",
        f"Количество объектов: {len(objects.get(obj_type, {}))}",
        f"",
    ]

    items = sorted(objects.get(obj_type, {}).items(), key=lambda x: x[0].lower())

    for obj_name, obj_data in items:
        fs_data = fs_structure.get(obj_type, {}).get(obj_name, {})
        lines.append(f"## {obj_name}\n")

        # Элементы (реквизиты, измерения и т.д.)
        elements = obj_data.get("elements", [])
        if elements:
            by_el_type = defaultdict(list)
            for el in elements:
                by_el_type[el["type"]].append(el["name"])
            for el_type, names in sorted(by_el_type.items()):
                display = names[:15]
                suffix = f" и еще {len(names) - 15}" if len(names) > 15 else ""
                lines.append(f"- **{el_type}**: {', '.join(display)}{suffix}")
            lines.append("")

        # Формы
        forms = fs_data.get("forms", [])
        if forms:
            lines.append(f"- **Формы**: {', '.join(forms)}")

        # Модули
        modules = fs_data.get("modules", [])
        if modules:
            lines.append(f"- **Модули**: {', '.join(modules)}")

        # Команды
        commands = fs_data.get("commands", [])
        if commands:
            lines.append(f"- **Команды**: {', '.join(commands)}")

        # Макеты
        templates = fs_data.get("templates", [])
        if templates:
            lines.append(f"- **Макеты**: {', '.join(templates)}")

        lines.append("")

    type_path = Path(output_path) / filename
    type_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Создан: {type_path}")


def generate_modules_graph(graph, module_info, output_path):
    """Генерирует граф зависимостей модулей."""
    lines = [
        "# Граф зависимостей модулей",
        "",
        "Показаны вызовы между общими модулями и другими объектами.",
        "",
    ]

    # Только для модулей, у которых есть информация
    for module_name in sorted(graph.keys()):
        called = graph[module_name]
        info = module_info.get(f"CommonModule.{module_name}", {})
        if not info and module_name in module_info:
            info = module_info[module_name]

        lines.append(f"## {module_name}\n")
        if info.get("procedures"):
            lines.append(f"- **Экспортные методы**: {', '.join(info['procedures'][:10])}")
        if info.get("size_lines"):
            lines.append(f"- **Строк кода**: {info['size_lines']}")
        if called:
            lines.append(f"- **Вызывает**: {', '.join(called[:20])}")
            if len(called) > 20:
                lines.append(f"  *(и еще {len(called) - 20} модулей)*")
        lines.append("")

    graph_path = Path(output_path) / "modules_graph.md"
    graph_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Создан: {graph_path}")


def generate_search_keywords(objects, output_path):
    """Генерирует файл ключевых слов для быстрого поиска."""
    keywords = defaultdict(list)

    for obj_type, items in objects.items():
        for obj_name in items:
            # Добавляем по первым буквам и ключевым частям имени
            words = re.findall(r'[А-Яа-яA-Za-z][а-яa-z]*', obj_name)
            for word in words:
                keywords[word.lower()].append(f"{obj_type}.{obj_name}")

    lines = ["# Ключевые слова для поиска", "", "| Ключевое слово | Объекты |", "|----------------|---------|"]
    for word, refs in sorted(keywords.items(), key=lambda x: -len(x[1]))[:500]:
        display = refs[:5]
        suffix = f" (+{len(refs) - 5})" if len(refs) > 5 else ""
        lines.append(f"| {word} | {', '.join(display)}{suffix} |")

    kw_path = Path(output_path) / "keywords.md"
    kw_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Создан: {kw_path}")


def main():
    parser = argparse.ArgumentParser(description="Генератор репозиторных карт для 1С")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Путь к конфигурации 1С")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Путь для сохранения карт")
    parser.add_argument("--max-modules", type=int, default=500, help="Макс. число модулей для анализа")
    args = parser.parse_args()

    config_path = args.config
    output_path = args.output

    print(f"Анализ конфигурации: {config_path}")
    print(f"Выходная директория: {output_path}")
    print("-" * 50)

    os.makedirs(output_path, exist_ok=True)

    # 1. Парсим ConfigDumpInfo.xml
    print("\n[1/6] Парсинг ConfigDumpInfo.xml...")
    objects = parse_config_dump_info(config_path)
    print(f"      Найдено типов объектов: {len(objects)}")
    total_objs = sum(len(v) for v in objects.values())
    print(f"      Всего объектов: {total_objs}")

    # 2. Сканируем файловую систему
    print("\n[2/6] Сканирование файловой системы...")
    fs_structure = scan_file_system(config_path)
    total_fs = sum(len(v) for v in fs_structure.values())
    print(f"      Найдено объектов в FS: {total_fs}")

    # 3. Анализируем модули
    print(f"\n[3/6] Анализ модулей (max={args.max_modules})...")
    graph, module_info = build_module_graph(config_path, fs_structure, max_files=args.max_modules)
    print(f"      Проанализировано модулей: {len(module_info)}")
    print(f"      Найдено зависимостей: {sum(len(v) for v in graph.values())}")

    # 4. Парсим подсистемы
    print("\n[4/6] Парсинг подсистем...")
    subsystems = parse_subsystems(config_path, fs_structure)
    print(f"      Корневых подсистем: {len(subsystems)}")

    # 5. Генерируем карты
    print("\n[5/6] Генерация markdown-файлов...")
    generate_readme(config_path, objects, output_path)
    generate_objects_index(objects, fs_structure, output_path)
    generate_subsystems_map(subsystems, output_path)
    generate_modules_graph(graph, module_info, output_path)
    generate_search_keywords(objects, output_path)

    # Карты по типам для основных объектов
    for obj_type in ["Catalog", "Document", "InformationRegister", "CommonModule", "DataProcessor", "Report"]:
        if obj_type in objects:
            generate_type_map(obj_type, objects, fs_structure, output_path)

    print("\n[6/6] Готово!")

    # Выводим статистику по размерам
    total_size = 0
    for f in Path(output_path).rglob("*.md"):
        total_size += f.stat().st_size
    print(f"\nОбщий размер карт: {total_size / 1024:.1f} КБ")
    print(f"Файлов карт: {len(list(Path(output_path).rglob('*.md')))}")


if __name__ == "__main__":
    main()
