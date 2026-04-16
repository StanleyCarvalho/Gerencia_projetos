import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BuildSmokeTestCase(unittest.TestCase):
    def test_python_core_files_are_valid(self):
        arquivos = [
            ROOT / "app.py",
            ROOT / "config.py",
            ROOT / "db.py",
            ROOT / "services" / "ia_service.py",
        ]

        for caminho in arquivos:
            codigo = caminho.read_text(encoding="utf-8")
            try:
                ast.parse(codigo)
            except SyntaxError as exc:
                self.fail(f"Erro de sintaxe em {caminho}: {exc}")

    def test_health_route_exists_in_app(self):
        app_path = ROOT / "app.py"
        tree = ast.parse(app_path.read_text(encoding="utf-8"))

        encontrou = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name != "health":
                continue

            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                if not isinstance(dec.func, ast.Attribute):
                    continue
                if dec.func.attr != "route":
                    continue
                if not isinstance(dec.func.value, ast.Name) or dec.func.value.id != "app":
                    continue
                if dec.args and isinstance(dec.args[0], ast.Constant) and dec.args[0].value == "/health":
                    encontrou = True
                    break

        self.assertTrue(encontrou, "Rota /health nao encontrada no app.py")

    def test_main_template_exists(self):
        self.assertTrue((ROOT / "templates" / "mapa_criticidade.html").exists())


if __name__ == "__main__":
    unittest.main()
