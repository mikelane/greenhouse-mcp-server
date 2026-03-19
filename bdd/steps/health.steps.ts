import { Given, When, Then } from '@cucumber/cucumber';
import { ServerWorld } from './support/world';
import * as assert from 'assert';

// --- Meta-testing steps (used by sub-cucumber runs) ---

Given('a trivial truth', function () {
  assert.ok(true);
});

Given('a deliberate failure', function () {
  assert.fail('This step intentionally fails');
});

// --- Server health check steps ---

Given('a running Python test server', async function (this: ServerWorld) {
  assert.ok(
    this.serverPort !== null,
    'Server did not start — no port assigned'
  );
});

When('I request GET {word}', async function (this: ServerWorld, urlPath: string) {
  // Cucumber {word} captures don't include the leading slash from the feature file
  // when the path is written as "/health". But {word} matches non-whitespace,
  // so "/health" is captured as "/health" (the slash is part of the word).
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

Given(
  'a feature file with a passing scenario',
  function (this: ServerWorld) {
    // Store the feature content for the "When cucumber-js runs" step
    (this as ServerWorld & { _featureContent: string })._featureContent = [
      'Feature: Pass test',
      '  Scenario: Always passes',
      '    Given a trivial truth',
    ].join('\n');
  }
);

Given(
  'a feature file with a failing assertion',
  function (this: ServerWorld) {
    (this as ServerWorld & { _featureContent: string })._featureContent = [
      'Feature: Fail test',
      '  Scenario: Always fails',
      '    Given a deliberate failure',
    ].join('\n');
  }
);

When('cucumber-js runs', function (this: ServerWorld) {
  const content = (this as ServerWorld & { _featureContent: string })
    ._featureContent;
  assert.ok(content, 'No feature content was set');
  this.lastCucumberResult = this.runCucumberOnFeature(content);
});

Then('the exit code is {int}', function (this: ServerWorld, expected: number) {
  assert.ok(this.lastCucumberResult, 'No cucumber result recorded');
  assert.strictEqual(this.lastCucumberResult.exitCode, expected);
});

Then('the exit code is non-zero', function (this: ServerWorld) {
  assert.ok(this.lastCucumberResult, 'No cucumber result recorded');
  assert.notStrictEqual(
    this.lastCucumberResult.exitCode,
    0,
    'Expected non-zero exit code'
  );
});

Then(
  'the output contains the assertion error',
  function (this: ServerWorld) {
    assert.ok(this.lastCucumberResult, 'No cucumber result recorded');
    // Cucumber outputs assertion errors with "AssertionError" or similar
    const output = this.lastCucumberResult.output;
    const hasError =
      output.includes('AssertionError') ||
      output.includes('Error') ||
      output.includes('failed') ||
      output.includes('undefined');
    assert.ok(
      hasError,
      `Expected output to contain an error indicator, got: ${output}`
    );
  }
);
