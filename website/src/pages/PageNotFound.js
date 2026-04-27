import * as React from "react";
import { Container, ContentLayout, Header } from "@cloudscape-design/components";
import { Link } from "react-router-dom";

export default function PageNotFound() {
  return (
    <ContentLayout header={<Header variant="h1">Page Not Found</Header>}>
      <Container>
        Not sure how you ended up here. <Link to="/">Go home.</Link>
      </Container>
    </ContentLayout>
  );
}
