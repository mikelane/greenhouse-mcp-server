import { World, setWorldConstructor, Before, After } from '@cucumber/cucumber';
import { ChildProcess, spawn, execSync } from 'child_process';
import * as path from 'path';

interface HttpResponse {
  status: number;
  body: string;
}

interface CucumberRunResult {
  exitCode: number;
  output: string;
}

export class ServerWorld extends World {
  serverProcess: ChildProcess | null = null;
  serverPort: number | null = null;
  lastResponse: HttpResponse | null = null;
  lastCucumberResult: CucumberRunResult | null = null;

  async startServer(): Promise<void> {
    const repoRoot = path.resolve(__dirname, '..', '..', '..');
    const serverScript = path.join(repoRoot, 'test_server.py');

    return new Promise<void>((resolve, reject) => {
      const proc = spawn('python3', [serverScript, '--port', '0'], {
        cwd: repoRoot,
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      this.serverProcess = proc;

      const timeout = setTimeout(() => {
        proc.kill('SIGKILL');
        reject(new Error('Server failed to start within 5 seconds'));
      }, 5000);

      proc.stdout!.on('data', (data: Buffer) => {
        const line = data.toString().trim();
        const match = line.match(/^PORT=(\d+)$/);
        if (match) {
          this.serverPort = parseInt(match[1], 10);
          clearTimeout(timeout);
          this.waitForReady()
            .then(() => resolve())
            .catch((err) => {
              clearTimeout(timeout);
              reject(err);
            });
        }
      });

      proc.stderr!.on('data', (data: Buffer) => {
        process.stderr.write(`[test_server stderr] ${data.toString()}`);
      });

      proc.on('error', (err) => {
        clearTimeout(timeout);
        reject(new Error(`Failed to spawn server: ${err.message}`));
      });

      proc.on('exit', (code, signal) => {
        clearTimeout(timeout);
        if (this.serverPort === null) {
          reject(
            new Error(
              `Server exited before reporting port (code=${code}, signal=${signal})`
            )
          );
        }
      });
    });
  }

  async waitForReady(): Promise<void> {
    const maxRetries = 10;
    const retryDelay = 100;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const response = await this.httpGet('/health');
        if (response.status === 200) {
          return;
        }
      } catch {
        // Server not ready yet
      }
      await new Promise((r) => setTimeout(r, retryDelay));
    }

    throw new Error(
      `Server on port ${this.serverPort} did not become ready after ${maxRetries} retries`
    );
  }

  async stopServer(): Promise<void> {
    if (!this.serverProcess) return;

    const proc = this.serverProcess;
    this.serverProcess = null;
    this.serverPort = null;

    return new Promise<void>((resolve) => {
      const killTimeout = setTimeout(() => {
        proc.kill('SIGKILL');
        resolve();
      }, 3000);

      proc.on('exit', () => {
        clearTimeout(killTimeout);
        resolve();
      });

      proc.kill('SIGTERM');
    });
  }

  async httpGet(urlPath: string): Promise<HttpResponse> {
    if (this.serverPort === null) {
      throw new Error('Server is not running (no port assigned)');
    }

    const url = `http://127.0.0.1:${this.serverPort}${urlPath}`;
    const response = await fetch(url);
    const body = await response.text();

    return { status: response.status, body };
  }

  runCucumberOnFeature(featureContent: string): CucumberRunResult {
    const fs = require('fs');
    const os = require('os');

    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bdd-test-'));
    const featureFile = path.join(tmpDir, 'test.feature');
    fs.writeFileSync(featureFile, featureContent);

    const bddDir = path.resolve(__dirname, '..', '..');
    const cucumberBin = path.join(bddDir, 'node_modules', '.bin', 'cucumber-js');

    try {
      const output = execSync(
        `"${cucumberBin}" --require-module ts-node/register --require "${path.join(bddDir, 'steps/**/*.ts')}" "${featureFile}"`,
        {
          cwd: bddDir,
          encoding: 'utf-8',
          stdio: ['ignore', 'pipe', 'pipe'],
          timeout: 15000,
        }
      );
      return { exitCode: 0, output };
    } catch (err: unknown) {
      const execErr = err as { status: number; stdout: string; stderr: string };
      return {
        exitCode: execErr.status ?? 1,
        output: (execErr.stdout || '') + (execErr.stderr || ''),
      };
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  }
}

setWorldConstructor(ServerWorld);

Before({ tags: '@bdd-infra' }, async function (this: ServerWorld) {
  await this.startServer();
});

After({ tags: '@bdd-infra' }, async function (this: ServerWorld) {
  await this.stopServer();
});
