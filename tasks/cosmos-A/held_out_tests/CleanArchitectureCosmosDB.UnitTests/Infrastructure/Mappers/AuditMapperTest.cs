using CleanArchitectureCosmosDB.Core.Entities;
using CleanArchitectureCosmosDB.Infrastructure.CosmosDbData.Mappers;
using CleanArchitectureCosmosDB.Infrastructure.CosmosDbData.Models;
using System;
using Xunit;

namespace CleanArchitectureCosmosDB.UnitTests.Infrastructure.Mappers
{
    public class AuditMapperTest
    {
        [Fact]
        public void ToDocument_MapsAllProperties()
        {
            var entity = new Audit("ToDoItem", "cat:123", "{\"Title\":\"Test\"}")
            {
                Id = "cat:123:guid-1"
            };

            var document = AuditMapper.ToDocument(entity);

            Assert.Equal("cat:123:guid-1", document.Id);
            Assert.Equal("ToDoItem", document.EntityType);
            Assert.Equal("cat:123", document.EntityId);
            Assert.Equal("{\"Title\":\"Test\"}", document.Entity);
            Assert.Equal(entity.DateCreatedUTC, document.DateCreatedUtc);
            Assert.Equal("audit", document.Type);
        }

        [Fact]
        public void ToDomain_MapsAllProperties()
        {
            var document = new AuditDocument
            {
                Id = "cat:456:guid-2",
                EntityType = "ToDoItem",
                EntityId = "cat:456",
                Entity = "{\"Title\":\"Test2\"}",
                DateCreatedUtc = new DateTime(2023, 6, 15, 10, 30, 0, DateTimeKind.Utc),
                Type = "audit",
                Etag = "some-etag"
            };

            var entity = AuditMapper.ToDomain(document);

            Assert.Equal("cat:456:guid-2", entity.Id);
            Assert.Equal("ToDoItem", entity.EntityType);
            Assert.Equal("cat:456", entity.EntityId);
            Assert.Equal("{\"Title\":\"Test2\"}", entity.Entity);
            Assert.Equal(new DateTime(2023, 6, 15, 10, 30, 0, DateTimeKind.Utc), entity.DateCreatedUTC);
        }

        [Fact]
        public void ToDomain_OverwritesConstructorDate()
        {
            var specificDate = new DateTime(2020, 1, 1, 0, 0, 0, DateTimeKind.Utc);
            var document = new AuditDocument
            {
                Id = "cat:789:guid-3",
                EntityType = "ToDoItem",
                EntityId = "cat:789",
                Entity = "{}",
                DateCreatedUtc = specificDate
            };

            var entity = AuditMapper.ToDomain(document);

            Assert.Equal(specificDate, entity.DateCreatedUTC);
        }

        [Fact]
        public void Roundtrip_PreservesData()
        {
            var original = new Audit("ToDoItem", "cat:001", "{\"Title\":\"Roundtrip\"}")
            {
                Id = "cat:001:guid-4"
            };

            var document = AuditMapper.ToDocument(original);
            var restored = AuditMapper.ToDomain(document);

            Assert.Equal(original.Id, restored.Id);
            Assert.Equal(original.EntityType, restored.EntityType);
            Assert.Equal(original.EntityId, restored.EntityId);
            Assert.Equal(original.Entity, restored.Entity);
            Assert.Equal(original.DateCreatedUTC, restored.DateCreatedUTC);
        }
    }
}
