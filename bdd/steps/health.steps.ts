import { Given, When, Then } from '@cucumber/cucumber';
import { ServerWorld } from './support/world';
import { strict as assert } from 'node:assert';

Given('a running Python test server', async function (this: ServerWorld) {
  assert.ok(
    this.serverPort !== null,
    'Server did not start — no port assigned'
  );
});

When('I request GET {word}', async function (this: ServerWorld, urlPath: string) {
  this.lastResponse = await this.httpGet(urlPath);
});

Then(
  'the response status is {int}',
  function (this: ServerWorld, expectedStatus: number) {
    assert.ok(this.lastResponse, 'No response recorded');
    assert.strictEqual(this.lastResponse.status, expectedStatus);
  }
);

Then(
  'the response body contains {string}',
  function (this: ServerWorld, expectedText: string) {
    assert.ok(this.lastResponse, 'No response recorded');
    assert.ok(
      this.lastResponse.body.includes(expectedText),
      `Expected body to contain "${expectedText}", got: ${this.lastResponse.body}`
    );
  }
);
