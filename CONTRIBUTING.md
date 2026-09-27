# Contributing to Classroom to Calendar & AI Sync 🚀

Thank you for your interest in contributing to Google Classroom to Calendar Sync!

## 🛠️ Development Setup

1. **Fork and Clone the Repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/classroom-to-calendar-sync.git
   cd classroom-to-calendar-sync
   ```

2. **Create a Virtual Environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run the Test Suite:**
   ```bash
   pytest -v
   ```

## 🧪 Testing Guidelines

- Write unit tests for new features in the `tests/` directory.
- Ensure all tests pass before opening a Pull Request (`pytest`).
- Maintain mock separation for network and API client calls so tests remain fast and deterministic.

## 📝 Pull Request Process

1. Create a feature branch (`git checkout -b feature/amazing-feature`).
2. Commit your changes with clear, descriptive commit messages.
3. Push to your branch (`git push origin feature/amazing-feature`).
4. Open a Pull Request detailing your changes, motivation, and test verification.

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.
