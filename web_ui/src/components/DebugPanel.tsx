import { Accordion, Badge, Card, Code, Group, Stack, Text, Title } from "@mantine/core";

import type { TestResponse } from "../api";


type DebugPanelProps = {
  debug: TestResponse["debug"];
};


export function DebugPanel({ debug }: DebugPanelProps) {
  const defaultItem = debug.validation_error ? "validation" : "validator";

  return (
    <Card className="debug-card">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <div>
            <Title order={3}>Debug</Title>
            <Text size="sm" c="dimmed">
              Final action: <Code>{debug.final_action}</Code>
            </Text>
          </div>
          <Badge variant="light" color={debug.validation_error ? "red" : "blue"}>
            {debug.validation_error ? "validation issue" : "valid"}
          </Badge>
        </Group>

        <Accordion variant="contained" radius="sm" defaultValue={defaultItem}>
          <Accordion.Item value="validator">
            <Accordion.Control>Validator</Accordion.Control>
            <Accordion.Panel>
              <pre className="json-block">{JSON.stringify(debug.validator_result, null, 2)}</pre>
            </Accordion.Panel>
          </Accordion.Item>
          <Accordion.Item value="raw">
            <Accordion.Control>Raw output</Accordion.Control>
            <Accordion.Panel>
              <pre className="json-block pre-wrap">{debug.raw_model_output || "-"}</pre>
            </Accordion.Panel>
          </Accordion.Item>
          <Accordion.Item value="validation">
            <Accordion.Control>Validation error</Accordion.Control>
            <Accordion.Panel>
              <pre className="json-block pre-wrap">{debug.validation_error || "-"}</pre>
            </Accordion.Panel>
          </Accordion.Item>
          <Accordion.Item value="prompt">
            <Accordion.Control>Prompt</Accordion.Control>
            <Accordion.Panel>
              <pre className="json-block pre-wrap">{debug.serialized_prompt || "-"}</pre>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      </Stack>
    </Card>
  );
}
