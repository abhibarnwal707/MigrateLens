package example;

import java.util.Map;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.SendMessageRequest;

public class OrderService {
    private final S3Client s3 = S3Client.create();
    private final DynamoDbClient ddb = DynamoDbClient.create();
    private final SqsClient sqs = SqsClient.create();
    private final String bucket = System.getenv("S3_BUCKET");
    private final String queueUrl = System.getenv("SQS_QUEUE_URL");

    public void placeOrder(String orderId, String body) {
        s3.putObject(PutObjectRequest.builder().bucket(bucket).key(orderId + ".json").build(),
                RequestBody.fromString(body));
        ddb.putItem(PutItemRequest.builder().tableName("orders")
                .item(Map.of("orderId", AttributeValue.fromS(orderId))).build());
        sqs.sendMessage(SendMessageRequest.builder().queueUrl(queueUrl).messageBody(orderId).build());
    }
}
