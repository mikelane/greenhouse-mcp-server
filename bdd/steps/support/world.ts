import { World, setWorldConstructor, Before, After } from '@cucumber/cucumber';
import { ChildProcess, spawn } from 'child_process';
import * as path from 'path';

interface HttpResponse {
  status: number;
  body: string;
}

export class ServerWorld extends World {
  serverProcess: ChildProcess | null = null;
  serverPort: number | null = null;
  lastResponse: HttpResponse | null = null;

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

}

setWorldConstructor(ServerWorld);

Before({ tags: '@bdd-infra' }, async function (this: ServerWorld) {
  await this.startServer();
});

After({ tags: '@bdd-infra' }, async function (this: ServerWorld) {
  await this.stopServer();
});
